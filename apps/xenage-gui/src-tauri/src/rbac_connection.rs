use base64::engine::general_purpose::STANDARD as BASE64_STANDARD;
use base64::Engine;
use ed25519_dalek::{Signer, SigningKey};
use getrandom::getrandom;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};

#[derive(Deserialize)]
struct GuiConnectionConfig {
    control_plane_urls: Vec<String>,
    user_id: String,
    role: String,
    public_key: String,
    private_key: String,
}

#[derive(Serialize)]
pub struct RbacYamlResourceEntry {
    pub kind: String,
    pub name: String,
    pub yaml: String,
    pub manifest: Value,
}

fn sha256_bytes(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    format!("{:x}", hasher.finalize())
}

fn random_nonce_hex() -> Result<String, String> {
    let mut bytes = [0u8; 16];
    getrandom(&mut bytes).map_err(|error| format!("failed to generate nonce: {error}"))?;
    Ok(bytes
        .iter()
        .map(|value| format!("{value:02x}"))
        .collect::<String>())
}

fn decode_base64_32(label: &str, value: &str) -> Result<[u8; 32], String> {
    let bytes = BASE64_STANDARD
        .decode(value.as_bytes())
        .map_err(|error| format!("invalid {label}: {error}"))?;
    bytes
        .try_into()
        .map_err(|_| format!("{label} must decode to 32 bytes"))
}

fn parse_gui_connection_yaml(config_yaml: &str) -> Result<GuiConnectionConfig, String> {
    let mut fields: std::collections::HashMap<String, String> = std::collections::HashMap::new();
    let mut control_plane_urls: Vec<String> = vec![];
    let mut in_control_plane_urls = false;
    for line in config_yaml.lines() {
        let mut compact = line.trim_end().trim_start();
        if let Some((first_token, rest)) = compact.split_once(' ') {
            let looks_like_rfc3339 = first_token.len() >= 20
                && first_token.contains('T')
                && first_token.ends_with('Z')
                && first_token
                    .chars()
                    .all(|ch| ch.is_ascii_digit() || matches!(ch, '-' | ':' | '.' | 'T' | 'Z'));
            if looks_like_rfc3339 {
                compact = rest.trim_start();
            }
        }
        if compact.is_empty() || compact.starts_with('#') {
            continue;
        }
        if compact == "controlPlaneUrls:" || compact == "control_plane_urls:" {
            in_control_plane_urls = true;
            continue;
        }
        if in_control_plane_urls && compact.starts_with("- ") {
            control_plane_urls.push(compact.trim_start_matches("- ").trim().to_string());
            continue;
        }
        if in_control_plane_urls && !compact.starts_with("- ") {
            in_control_plane_urls = false;
        }
        let Some((key, value)) = compact.split_once(':') else {
            continue;
        };
        fields.insert(
            key.trim().to_string(),
            value
                .trim()
                .trim_matches('"')
                .trim_matches('\'')
                .to_string(),
        );
    }

    if control_plane_urls.is_empty() {
        if let Some(single_url) = fields
            .get("controlPlaneUrl")
            .or_else(|| fields.get("control_plane_url"))
            .cloned()
        {
            control_plane_urls.push(single_url);
        }
    }
    if control_plane_urls.is_empty() {
        return Err("missing controlPlaneUrls".to_string());
    }

    let user_id = fields
        .get("id")
        .or_else(|| fields.get("user_id"))
        .cloned()
        .unwrap_or_else(|| "admin".to_string());
    let role = fields
        .get("role")
        .cloned()
        .unwrap_or_else(|| "admin".to_string());
    let public_key = fields
        .get("publicKey")
        .or_else(|| fields.get("public_key"))
        .cloned()
        .ok_or_else(|| "missing publicKey".to_string())?;
    let private_key = fields
        .get("privateKey")
        .or_else(|| fields.get("private_key"))
        .cloned()
        .ok_or_else(|| "missing privateKey".to_string())?;

    Ok(GuiConnectionConfig {
        control_plane_urls,
        user_id,
        role,
        public_key,
        private_key,
    })
}

async fn signed_request(
    client: &reqwest::Client,
    method: reqwest::Method,
    base_url: &str,
    path: &str,
    body: &[u8],
    config: &GuiConnectionConfig,
    signing_key: &SigningKey,
) -> Result<(reqwest::StatusCode, String, String), String> {
    let timestamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_err(|error| error.to_string())?
        .as_secs() as i64;
    let nonce = random_nonce_hex()?;
    let payload = format!(
        "{}\n{}\n{}\n{}\n{}",
        method.as_str(),
        path,
        timestamp,
        nonce,
        sha256_bytes(body)
    );
    let signature = signing_key.sign(payload.as_bytes());
    let signature_b64 = BASE64_STANDARD.encode(signature.to_bytes());
    let url = format!("{}{}", base_url.trim_end_matches('/'), path);

    let mut request = client
        .request(method, &url)
        .header("x-node-id", &config.user_id)
        .header("x-timestamp", timestamp.to_string())
        .header("x-nonce", &nonce)
        .header("x-signature", &signature_b64)
        .header("x-public-key", &config.public_key);
    if !body.is_empty() {
        request = request.header("content-type", "application/json").body(body.to_vec());
    }

    let response = request
        .send()
        .await
        .map_err(|error| format!("{url}: {error}"))?;
    let status = response.status();
    let response_body = response.text().await.map_err(|error| error.to_string())?;
    Ok((status, response_body, url))
}

fn map_kind_to_resource(kind: &str) -> Result<(&str, &str), String> {
    if kind == "User" {
        return Ok(("serviceaccounts", "User"));
    }
    if kind == "Role" {
        return Ok(("roles", "Role"));
    }
    if kind == "RoleBinding" {
        return Ok(("rolebindings", "RoleBinding"));
    }
    Err(format!("unsupported RBAC kind: {kind}"))
}

pub async fn list_rbac_yaml_resources_from_yaml(
    config_yaml: String,
    kind: String,
) -> Result<Vec<RbacYamlResourceEntry>, String> {
    let config = parse_gui_connection_yaml(&config_yaml)?;
    if config.role != "admin" {
        return Err("only admin role is supported".to_string());
    }

    let private_key_bytes = decode_base64_32("private key", &config.private_key)?;
    let public_key_bytes = decode_base64_32("public key", &config.public_key)?;
    let signing_key = SigningKey::from_bytes(&private_key_bytes);
    if signing_key.verifying_key().to_bytes() != public_key_bytes {
        return Err("public key does not match private key".to_string());
    }

    let (resource, entry_kind) = map_kind_to_resource(&kind)?;
    let path = format!("/v1/resources/{resource}?namespace=cluster");

    let client = reqwest::Client::builder()
        .use_rustls_tls()
        .build()
        .map_err(|error| error.to_string())?;
    let mut errors: Vec<String> = vec![];

    for base in &config.control_plane_urls {
        let (status, body, url) = match signed_request(
            &client,
            reqwest::Method::GET,
            base,
            &path,
            &[],
            &config,
            &signing_key,
        )
        .await
        {
            Ok(value) => value,
            Err(error) => {
                errors.push(error);
                continue;
            }
        };

        if !status.is_success() {
            errors.push(format!(
                "{url}: control-plane rejected request ({status}): {body}"
            ));
            continue;
        }

        let decoded: Value = serde_json::from_str(&body)
            .map_err(|error| format!("invalid control-plane response: {error}"))?;
        let Some(items) = decoded.get("items").and_then(Value::as_array) else {
            return Ok(vec![]);
        };

        let mut entries: Vec<RbacYamlResourceEntry> = vec![];
        let mut index = 0usize;
        while index < items.len() {
            let item = &items[index];
            let name = item
                .get("metadata")
                .and_then(Value::as_object)
                .and_then(|metadata| metadata.get("name"))
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string();
            let yaml = serde_yaml::to_string(item)
                .map_err(|error| format!("failed to build YAML from resource: {error}"))?;
            entries.push(RbacYamlResourceEntry {
                kind: entry_kind.to_string(),
                name,
                yaml,
                manifest: item.clone(),
            });
            index += 1;
        }

        entries.sort_by(|a, b| a.name.cmp(&b.name));
        return Ok(entries);
    }

    Err(errors.join(" | "))
}

pub async fn apply_rbac_yaml_resource_from_yaml(
    config_yaml: String,
    manifest_yaml: String,
    delete_mode: bool,
) -> Result<Value, String> {
    let config = parse_gui_connection_yaml(&config_yaml)?;
    if config.role != "admin" {
        return Err("only admin role is supported".to_string());
    }

    let private_key_bytes = decode_base64_32("private key", &config.private_key)?;
    let public_key_bytes = decode_base64_32("public key", &config.public_key)?;
    let signing_key = SigningKey::from_bytes(&private_key_bytes);
    if signing_key.verifying_key().to_bytes() != public_key_bytes {
        return Err("public key does not match private key".to_string());
    }

    let mut manifest: Value = serde_yaml::from_str(&manifest_yaml)
        .map_err(|error| format!("invalid manifest YAML: {error}"))?;
    let Some(manifest_object) = manifest.as_object_mut() else {
        return Err("manifest must be a YAML object".to_string());
    };

    if delete_mode {
        let metadata = manifest_object
            .entry("metadata")
            .or_insert_with(|| Value::Object(serde_json::Map::new()));
        let Some(metadata_object) = metadata.as_object_mut() else {
            return Err("manifest.metadata must be an object".to_string());
        };
        let annotations = metadata_object
            .entry("annotations")
            .or_insert_with(|| Value::Object(serde_json::Map::new()));
        let Some(annotations_object) = annotations.as_object_mut() else {
            return Err("manifest.metadata.annotations must be an object".to_string());
        };
        annotations_object.insert(
            "xenage.io/action".to_string(),
            Value::String("delete".to_string()),
        );
    }

    let body = serde_json::to_vec(&manifest).map_err(|error| format!("failed to encode manifest: {error}"))?;
    let path = "/v1/resources/apply";
    let client = reqwest::Client::builder()
        .use_rustls_tls()
        .build()
        .map_err(|error| error.to_string())?;
    let mut errors: Vec<String> = vec![];

    for base in &config.control_plane_urls {
        let (status, response_body, url) = match signed_request(
            &client,
            reqwest::Method::POST,
            base,
            path,
            &body,
            &config,
            &signing_key,
        )
        .await
        {
            Ok(value) => value,
            Err(error) => {
                errors.push(error);
                continue;
            }
        };

        if status.is_success() {
            return serde_json::from_str(&response_body)
                .map_err(|error| format!("invalid control-plane response: {error}"));
        }

        errors.push(format!(
            "{url}: control-plane rejected request ({status}): {response_body}"
        ));
    }

    Err(errors.join(" | "))
}
