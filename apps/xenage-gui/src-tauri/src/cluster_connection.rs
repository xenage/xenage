use base64::engine::general_purpose::STANDARD as BASE64_STANDARD;
use base64::Engine;
use ed25519_dalek::{Signer, SigningKey};
use getrandom::getrandom;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{HashMap, HashSet};
use std::fs;
use std::path::PathBuf;

#[derive(Deserialize)]
struct GuiConnectionConfig {
    cluster_name: String,
    control_plane_urls: Vec<String>,
    user_id: String,
    role: String,
    public_key: String,
    private_key: String,
}

#[derive(Serialize)]
pub struct StoredClusterConnection {
    pub id: String,
    pub name: String,
    pub yaml: String,
}

#[derive(Serialize, Deserialize, Clone)]
pub struct ClusterUiPrefsEntry {
    pub connection_id: String,
    pub name: String,
    pub accent: String,
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
    let mut fields: HashMap<String, String> = HashMap::new();
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

    let cluster_name = fields
        .get("clusterName")
        .or_else(|| fields.get("cluster_name"))
        .cloned()
        .unwrap_or_else(|| "demo".to_string());
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
        cluster_name,
        control_plane_urls,
        user_id,
        role,
        public_key,
        private_key,
    })
}

fn dump_gui_connection_yaml(config: &GuiConnectionConfig) -> String {
    let config_name = format!("{}-{}", config.cluster_name, config.user_id)
        .to_ascii_lowercase()
        .replace('_', "-");
    let mut lines = vec![
        "apiVersion: xenage.io/v1alpha1".to_string(),
        "kind: ClusterConnection".to_string(),
        "metadata:".to_string(),
        format!("  name: {config_name}"),
        "spec:".to_string(),
        format!("  clusterName: {}", config.cluster_name),
        "  controlPlaneUrls:".to_string(),
    ];
    for url in &config.control_plane_urls {
        lines.push(format!("    - {url}"));
    }
    lines.extend([
        "  user:".to_string(),
        format!("    id: {}", config.user_id),
        format!("    role: {}", config.role),
        format!("    publicKey: {}", config.public_key),
        format!("    privateKey: {}", config.private_key),
    ]);
    format!("{}\n", lines.join("\n"))
}

fn merge_control_plane_urls(existing: &[String], discovered: &[String]) -> Vec<String> {
    let mut merged: Vec<String> = vec![];
    let mut seen: HashSet<String> = HashSet::new();
    for source in [existing, discovered] {
        for raw_url in source {
            let normalized = raw_url.trim().trim_end_matches('/').to_string();
            if normalized.is_empty() || !seen.insert(normalized.clone()) {
                continue;
            }
            merged.push(normalized);
        }
    }
    merged
}

fn connection_configs_dir() -> Result<PathBuf, String> {
    let dir = std::env::temp_dir()
        .join("xenage-gui")
        .join("cluster-connections");
    fs::create_dir_all(&dir).map_err(|error| error.to_string())?;
    Ok(dir)
}

fn cluster_connection_path_by_id(connection_id: &str) -> Result<PathBuf, String> {
    let dir = connection_configs_dir()?;
    let entries = fs::read_dir(&dir).map_err(|error| error.to_string())?;
    for entry_result in entries {
        let entry = entry_result.map_err(|error| error.to_string())?;
        let path = entry.path();
        if path.extension().and_then(|item| item.to_str()) != Some("yaml") {
            continue;
        }
        let stem = path
            .file_stem()
            .and_then(|item| item.to_str())
            .unwrap_or_default();
        if stem == connection_id {
            return Ok(path);
        }
    }
    Err(format!("Cluster connection not found: {connection_id}"))
}

fn cluster_ui_prefs_path() -> Result<PathBuf, String> {
    let dir = std::env::temp_dir().join("xenage-gui");
    fs::create_dir_all(&dir).map_err(|error| error.to_string())?;
    Ok(dir.join("cluster-ui-prefs.json"))
}

fn normalize_hex_color(value: &str) -> String {
    let trimmed = value.trim();
    let valid = trimmed.len() == 7
        && trimmed.starts_with('#')
        && trimmed.chars().skip(1).all(|ch| ch.is_ascii_hexdigit());
    if valid {
        trimmed.to_ascii_lowercase()
    } else {
        "#22c55e".to_string()
    }
}

async fn signed_gui_get(
    client: &reqwest::Client,
    base_url: &str,
    path: &str,
    config: &GuiConnectionConfig,
    signing_key: &SigningKey,
) -> Result<(reqwest::StatusCode, String, String), String> {
    let timestamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_err(|error| error.to_string())?
        .as_secs() as i64;
    let nonce = random_nonce_hex()?;
    let payload = format!(
        "GET\n{}\n{}\n{}\n{}",
        path,
        timestamp,
        nonce,
        sha256_bytes(&[])
    );
    let signature = signing_key.sign(payload.as_bytes());
    let signature_b64 = BASE64_STANDARD.encode(signature.to_bytes());
    let url = format!("{}{}", base_url.trim_end_matches('/'), path);
    let response = client
        .get(&url)
        .header("x-node-id", &config.user_id)
        .header("x-timestamp", timestamp.to_string())
        .header("x-nonce", &nonce)
        .header("x-signature", &signature_b64)
        .header("x-public-key", &config.public_key)
        .send()
        .await
        .map_err(|error| format!("{url}: {error}"))?;
    let status = response.status();
    let body = response.text().await.map_err(|error| error.to_string())?;
    Ok((status, body, url))
}

fn is_unsupported_events_route(status: reqwest::StatusCode, body: &str) -> bool {
    if !matches!(
        status,
        reqwest::StatusCode::UNAUTHORIZED
            | reqwest::StatusCode::NOT_FOUND
            | reqwest::StatusCode::BAD_REQUEST
    ) {
        return false;
    }
    let normalized = body.to_ascii_lowercase();
    normalized.contains("unsupported route") && normalized.contains("/v1/gui/events")
}

fn event_sequence(entry: &serde_json::Value) -> Option<i64> {
    entry.get("sequence").and_then(serde_json::Value::as_i64)
}

fn build_event_page_from_legacy_snapshot(
    snapshot: serde_json::Value,
    before_sequence: Option<i64>,
    limit: i64,
) -> Result<serde_json::Value, String> {
    let safe_limit = limit.clamp(1, 200) as usize;
    let event_log = snapshot
        .get("event_log")
        .and_then(serde_json::Value::as_array)
        .ok_or_else(|| "legacy /v1/gui/cluster response does not contain event_log".to_string())?;
    let mut entries: Vec<serde_json::Value> = event_log
        .iter()
        .filter(|entry| event_sequence(entry).is_some())
        .cloned()
        .collect();
    entries.sort_by_key(|entry| event_sequence(entry).unwrap_or(i64::MAX));

    let end_index = if let Some(before) = before_sequence {
        let mut left = 0usize;
        let mut right = entries.len();
        while left < right {
            let middle = (left + right) / 2;
            let sequence = event_sequence(&entries[middle]).unwrap_or(i64::MIN);
            if sequence < before {
                left = middle + 1;
            } else {
                right = middle;
            }
        }
        left
    } else {
        entries.len()
    };
    let start_index = end_index.saturating_sub(safe_limit);
    let mut items = entries[start_index..end_index].to_vec();
    items.reverse();
    let has_more = start_index > 0;
    let next_before_sequence = items.last().and_then(event_sequence).unwrap_or(0);
    Ok(serde_json::json!({
        "items": items,
        "has_more": has_more,
        "next_before_sequence": next_before_sequence
    }))
}

fn load_cluster_ui_prefs_file() -> Result<Vec<ClusterUiPrefsEntry>, String> {
    let path = cluster_ui_prefs_path()?;
    if !path.exists() {
        return Ok(vec![]);
    }
    let body = fs::read_to_string(path).map_err(|error| error.to_string())?;
    serde_json::from_str::<Vec<ClusterUiPrefsEntry>>(&body).map_err(|error| error.to_string())
}

fn save_cluster_ui_prefs_file(entries: &[ClusterUiPrefsEntry]) -> Result<(), String> {
    let path = cluster_ui_prefs_path()?;
    let body = serde_json::to_string_pretty(entries).map_err(|error| error.to_string())?;
    fs::write(path, body).map_err(|error| error.to_string())
}

fn safe_slug(value: &str) -> String {
    let slug: String = value
        .chars()
        .map(|ch| {
            if ch.is_ascii_alphanumeric() {
                ch.to_ascii_lowercase()
            } else {
                '-'
            }
        })
        .collect();
    slug.trim_matches('-').to_string()
}

pub async fn fetch_cluster_snapshot_from_yaml(
    config_yaml: String,
) -> Result<serde_json::Value, String> {
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

    let path = "/v1/gui/cluster";
    let client = reqwest::Client::builder()
        .use_rustls_tls()
        .build()
        .map_err(|error| error.to_string())?;
    let mut errors: Vec<String> = vec![];
    for base in &config.control_plane_urls {
        let (status, body, url) =
            match signed_gui_get(&client, base, path, &config, &signing_key).await {
                Ok(value) => value,
                Err(error) => {
                    errors.push(error);
                    continue;
                }
            };
        if status.is_success() {
            return serde_json::from_str(&body)
                .map_err(|error| format!("invalid control-plane response: {error}"));
        }
        errors.push(format!(
            "{url}: control-plane rejected request ({status}): {body}"
        ));
    }
    Err(errors.join(" | "))
}

pub async fn fetch_cluster_events_from_yaml(
    config_yaml: String,
    before_sequence: Option<i64>,
    limit: Option<i64>,
) -> Result<serde_json::Value, String> {
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

    let safe_limit = limit.unwrap_or(10).clamp(1, 200);
    let path = if let Some(before) = before_sequence {
        format!("/v1/gui/events?limit={safe_limit}&before_sequence={before}")
    } else {
        format!("/v1/gui/events?limit={safe_limit}")
    };

    let client = reqwest::Client::builder()
        .use_rustls_tls()
        .build()
        .map_err(|error| error.to_string())?;
    let mut errors: Vec<String> = vec![];
    let mut legacy_fallback_page: Option<serde_json::Value> = None;
    let mut saw_unsupported_events_route = false;
    for base in &config.control_plane_urls {
        let (status, body, url) =
            match signed_gui_get(&client, base, &path, &config, &signing_key).await {
                Ok(value) => value,
                Err(error) => {
                    errors.push(error);
                    continue;
                }
            };
        if status.is_success() {
            return serde_json::from_str(&body)
                .map_err(|error| format!("invalid control-plane response: {error}"));
        }
        if is_unsupported_events_route(status, &body) {
            saw_unsupported_events_route = true;
            if legacy_fallback_page.is_none() {
                let fallback_path = "/v1/gui/cluster";
                let (fallback_status, fallback_body, fallback_url) = match signed_gui_get(
                    &client,
                    base,
                    fallback_path,
                    &config,
                    &signing_key,
                )
                .await
                {
                    Ok(value) => value,
                    Err(error) => {
                        errors.push(format!(
                            "{url}: events endpoint unsupported, and legacy snapshot fallback request failed: {error}"
                        ));
                        continue;
                    }
                };
                if fallback_status.is_success() {
                    let fallback_page = serde_json::from_str::<serde_json::Value>(&fallback_body)
                        .map_err(|error| format!("invalid legacy snapshot response: {error}"))
                        .and_then(|snapshot| {
                            build_event_page_from_legacy_snapshot(
                                snapshot,
                                before_sequence,
                                safe_limit,
                            )
                        });
                    match fallback_page {
                        Ok(page) => {
                            legacy_fallback_page = Some(page);
                        }
                        Err(error) => {
                            errors.push(format!(
                                "{url}: events endpoint unsupported; legacy snapshot fallback decode failed: {error}"
                            ));
                        }
                    }
                    continue;
                }
                errors.push(format!(
                    "{url}: events endpoint unsupported; legacy snapshot fallback rejected ({fallback_status}) from {fallback_url}: {fallback_body}"
                ));
            }
            continue;
        }
        errors.push(format!(
            "{url}: control-plane rejected request ({status}): {body}"
        ));
    }
    if saw_unsupported_events_route {
        if let Some(page) = legacy_fallback_page {
            return Ok(page);
        }
    }
    Err(errors.join(" | "))
}

pub async fn sync_cluster_connection_control_plane_urls(
    connection_id: String,
    control_plane_urls: Vec<String>,
) -> Result<StoredClusterConnection, String> {
    let path = cluster_connection_path_by_id(&connection_id)?;
    let current_yaml = fs::read_to_string(&path).map_err(|error| error.to_string())?;
    let mut config = parse_gui_connection_yaml(&current_yaml)?;
    let merged_urls = merge_control_plane_urls(&config.control_plane_urls, &control_plane_urls);
    if merged_urls.is_empty() {
        return Err("control plane URL sync produced an empty URL list".to_string());
    }
    if merged_urls != config.control_plane_urls {
        config.control_plane_urls = merged_urls;
        let updated_yaml = dump_gui_connection_yaml(&config);
        fs::write(&path, &updated_yaml).map_err(|error| error.to_string())?;
        return Ok(StoredClusterConnection {
            id: connection_id,
            name: config.cluster_name,
            yaml: updated_yaml,
        });
    }
    Ok(StoredClusterConnection {
        id: connection_id,
        name: config.cluster_name,
        yaml: current_yaml,
    })
}

pub async fn save_cluster_connection_yaml(
    config_yaml: String,
) -> Result<StoredClusterConnection, String> {
    let config = parse_gui_connection_yaml(&config_yaml)?;
    let dir = connection_configs_dir()?;
    let base_name = format!(
        "{}-{}",
        safe_slug(&config.cluster_name),
        safe_slug(&config.user_id)
    );
    let hash = &sha256_bytes(config_yaml.as_bytes())[0..10];
    let file_name = format!("{base_name}-{hash}.yaml");
    let path = dir.join(file_name);
    fs::write(&path, config_yaml).map_err(|error| error.to_string())?;
    Ok(StoredClusterConnection {
        id: path
            .file_stem()
            .and_then(|item| item.to_str())
            .unwrap_or("connection")
            .to_string(),
        name: config.cluster_name,
        yaml: fs::read_to_string(path).map_err(|error| error.to_string())?,
    })
}

pub async fn list_cluster_connection_yamls() -> Result<Vec<StoredClusterConnection>, String> {
    let dir = connection_configs_dir()?;
    let mut output: Vec<StoredClusterConnection> = vec![];
    let entries = fs::read_dir(dir).map_err(|error| error.to_string())?;
    for entry_result in entries {
        let entry = entry_result.map_err(|error| error.to_string())?;
        let path = entry.path();
        if path.extension().and_then(|item| item.to_str()) != Some("yaml") {
            continue;
        }
        let yaml = fs::read_to_string(&path).map_err(|error| error.to_string())?;
        let config = match parse_gui_connection_yaml(&yaml) {
            Ok(value) => value,
            Err(_) => continue,
        };
        output.push(StoredClusterConnection {
            id: path
                .file_stem()
                .and_then(|item| item.to_str())
                .unwrap_or("connection")
                .to_string(),
            name: config.cluster_name,
            yaml,
        });
    }
    output.sort_by(|a, b| a.name.cmp(&b.name).then(a.id.cmp(&b.id)));
    Ok(output)
}

pub async fn list_cluster_ui_prefs() -> Result<Vec<ClusterUiPrefsEntry>, String> {
    load_cluster_ui_prefs_file()
}

pub async fn save_cluster_ui_prefs_entry(
    connection_id: String,
    name: String,
    accent: String,
) -> Result<ClusterUiPrefsEntry, String> {
    let mut entries = load_cluster_ui_prefs_file()?;
    let normalized = ClusterUiPrefsEntry {
        connection_id: connection_id.clone(),
        name: name.trim().to_string(),
        accent: normalize_hex_color(&accent),
    };

    if let Some(existing) = entries
        .iter_mut()
        .find(|entry| entry.connection_id == connection_id)
    {
        *existing = normalized.clone();
    } else {
        entries.push(normalized.clone());
    }

    entries.sort_by(|a, b| a.connection_id.cmp(&b.connection_id));
    save_cluster_ui_prefs_file(&entries)?;
    Ok(normalized)
}

pub async fn delete_cluster_connection(connection_id: String) -> Result<(), String> {
    let dir = connection_configs_dir()?;
    let mut removed = false;
    let entries = fs::read_dir(&dir).map_err(|error| error.to_string())?;
    for entry_result in entries {
        let entry = entry_result.map_err(|error| error.to_string())?;
        let path = entry.path();
        if path.extension().and_then(|item| item.to_str()) != Some("yaml") {
            continue;
        }
        let stem = path
            .file_stem()
            .and_then(|item| item.to_str())
            .unwrap_or_default();
        if stem == connection_id {
            fs::remove_file(&path).map_err(|error| error.to_string())?;
            removed = true;
            break;
        }
    }

    if !removed {
        return Err(format!("Cluster connection not found: {connection_id}"));
    }

    let mut ui_entries = load_cluster_ui_prefs_file()?;
    ui_entries.retain(|entry| entry.connection_id != connection_id);
    save_cluster_ui_prefs_file(&ui_entries)?;
    Ok(())
}
