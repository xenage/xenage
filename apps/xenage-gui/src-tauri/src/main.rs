// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use flate2::read::GzDecoder;
use base64::Engine;
use base64::engine::general_purpose::STANDARD as BASE64_STANDARD;
use ed25519_dalek::{Signer, SigningKey};
use getrandom::getrandom;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fs;
use std::io::Cursor;
use std::path::{Path, PathBuf};
use std::process::Command;
use tauri::{AppHandle, Emitter, Manager};
use tauri_plugin_updater::UpdaterExt;
use url::Url;

const STABLE_UPDATE_ENDPOINT: &str =
    "https://github.com/xenage/xenage/releases/latest/download/latest.json";
const DEV_UPDATE_ENDPOINT: &str =
    "https://github.com/xenage/xenage/releases/download/xenage-gui-dev/latest.json";
const STANDALONE_STABLE_BASE: &str =
    "https://github.com/xenage/xenage/releases/download/xenage-standalone-main";
const STANDALONE_DEV_BASE: &str =
    "https://github.com/xenage/xenage/releases/download/xenage-standalone-dev";

#[derive(Serialize)]
struct UpdateMetadata {
    current_version: String,
    version: String,
    notes: Option<String>,
    pub_date: Option<String>,
    target: String,
}

#[derive(Clone, Serialize)]
struct UpdateLogEvent {
    channel: String,
    endpoint: String,
    step: String,
    message: String,
    force: bool,
    current_version: Option<String>,
    version: Option<String>,
    target: Option<String>,
    downloaded_bytes: Option<usize>,
    content_length: Option<u64>,
}

#[derive(Clone, Serialize)]
struct StandaloneLogEvent {
    channel: String,
    asset: String,
    step: String,
    message: String,
}

#[derive(Clone, Serialize)]
struct ServiceStatus {
    state: String,
    details: Option<String>,
}

#[derive(Serialize)]
struct StandaloneStatus {
    installed: bool,
    install_dir: String,
    asset_name: String,
    version: Option<String>,
    control_plane_service: ServiceStatus,
    runtime_service: ServiceStatus,
}

#[derive(Serialize)]
struct StandaloneInstallResult {
    version: String,
    install_dir: String,
    asset_name: String,
}

#[derive(Deserialize)]
struct StandaloneManifest {
    version: String,
}

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
struct StoredClusterConnection {
    id: String,
    name: String,
    yaml: String,
}

#[derive(Serialize, Deserialize, Clone)]
struct ClusterUiPrefsEntry {
    connection_id: String,
    name: String,
    accent: String,
}

enum NodeRole {
    ControlPlane,
    Runtime,
}

impl NodeRole {
    fn parse(value: &str) -> Result<Self, String> {
        match value {
            "control-plane" => Ok(Self::ControlPlane),
            "runtime" => Ok(Self::Runtime),
            _ => Err(format!("Unknown node role: {value}")),
        }
    }

    fn binary_name(&self) -> &'static str {
        match self {
            Self::ControlPlane => "xenage-control-plane",
            Self::Runtime => "xenage-runtime",
        }
    }

    fn service_slug(&self) -> &'static str {
        match self {
            Self::ControlPlane => "control-plane",
            Self::Runtime => "runtime",
        }
    }

    fn service_title(&self) -> &'static str {
        match self {
            Self::ControlPlane => "Control Plane",
            Self::Runtime => "Runtime",
        }
    }
}

fn update_endpoint(channel: &str) -> &'static str {
    match channel {
        "dev" => DEV_UPDATE_ENDPOINT,
        _ => STABLE_UPDATE_ENDPOINT,
    }
}

fn standalone_base_endpoint(channel: &str) -> &'static str {
    match channel {
        "dev" => STANDALONE_DEV_BASE,
        _ => STANDALONE_STABLE_BASE,
    }
}

fn emit_update_log(app: &AppHandle, event: UpdateLogEvent) {
    let log_line = format!(
        "[updater:{}:{}] {}",
        event.channel, event.step, event.message
    );
    println!("{log_line}");

    if let Err(error) = app.emit("updater://log", event) {
        eprintln!("failed to emit updater log event: {error}");
    }
}

fn emit_standalone_log(app: &AppHandle, event: StandaloneLogEvent) {
    let log_line = format!(
        "[standalone:{}:{}] {}",
        event.channel, event.step, event.message
    );
    println!("{log_line}");

    if let Err(error) = app.emit("standalone://log", event) {
        eprintln!("failed to emit standalone log event: {error}");
    }
}

async fn fetch_update(
    app: &AppHandle,
    channel: &str,
    force: bool,
) -> Result<Option<tauri_plugin_updater::Update>, String> {
    let endpoint = Url::parse(update_endpoint(channel)).map_err(|error| error.to_string())?;
    let endpoint_string = endpoint.to_string();

    emit_update_log(
        app,
        UpdateLogEvent {
            channel: channel.to_string(),
            endpoint: endpoint_string.clone(),
            step: "check-started".into(),
            message: format!("Checking {channel} channel against {endpoint_string}"),
            force,
            current_version: None,
            version: None,
            target: None,
            downloaded_bytes: None,
            content_length: None,
        },
    );

    let mut builder = app
        .updater_builder()
        .endpoints(vec![endpoint])
        .map_err(|error| error.to_string())?;

    if force {
        builder = builder.version_comparator(|_, _| true);
    }

    let updater = builder.build().map_err(|error| error.to_string())?;
    let update = updater.check().await.map_err(|error| error.to_string())?;

    match &update {
        Some(update) => emit_update_log(
            app,
            UpdateLogEvent {
                channel: channel.to_string(),
                endpoint: endpoint_string,
                step: "update-found".into(),
                message: format!(
                    "Update {} available for current version {} and target {}",
                    update.version, update.current_version, update.target
                ),
                force,
                current_version: Some(update.current_version.clone()),
                version: Some(update.version.clone()),
                target: Some(update.target.clone()),
                downloaded_bytes: None,
                content_length: None,
            },
        ),
        None => emit_update_log(
            app,
            UpdateLogEvent {
                channel: channel.to_string(),
                endpoint: endpoint_string,
                step: "no-update".into(),
                message: "No update available for current channel".into(),
                force,
                current_version: None,
                version: None,
                target: None,
                downloaded_bytes: None,
                content_length: None,
            },
        ),
    }

    Ok(update)
}

fn standalone_asset_name() -> Result<String, String> {
    let os = std::env::consts::OS;
    let arch = std::env::consts::ARCH;
    let extension = if os == "windows" { "zip" } else { "tar.gz" };

    if !matches!(os, "linux" | "macos" | "windows") {
        return Err(format!("Unsupported OS for standalone package: {os}"));
    }

    Ok(format!("xenage-standalone-{os}-{arch}.{extension}"))
}

fn standalone_root(app: &AppHandle) -> Result<PathBuf, String> {
    let app_data = app.path().app_data_dir().map_err(|error| error.to_string())?;
    let root = app_data.join("standalone");
    fs::create_dir_all(&root).map_err(|error| error.to_string())?;
    Ok(root)
}

fn standalone_bin_dir(app: &AppHandle) -> Result<PathBuf, String> {
    let dir = standalone_root(app)?.join("bin");
    fs::create_dir_all(&dir).map_err(|error| error.to_string())?;
    Ok(dir)
}

fn manifest_path(app: &AppHandle) -> Result<PathBuf, String> {
    Ok(standalone_root(app)?.join("standalone-manifest.json"))
}

fn installed_binary_path(app: &AppHandle, role: &NodeRole) -> Result<PathBuf, String> {
    let extension = if std::env::consts::OS == "windows" {
        ".exe"
    } else {
        ""
    };
    let path = standalone_bin_dir(app)?.join(format!("{}{}", role.binary_name(), extension));
    if !path.exists() {
        return Err(format!(
            "Standalone binary is missing. Install standalone package first: {}",
            path.display()
        ));
    }

    Ok(path)
}

fn parse_checksum(body: &str) -> Result<String, String> {
    let token = body
        .split_whitespace()
        .next()
        .ok_or_else(|| "Checksum payload is empty".to_string())?;
    if token.len() != 64 || !token.chars().all(|ch| ch.is_ascii_hexdigit()) {
        return Err("Checksum format is invalid".to_string());
    }
    Ok(token.to_lowercase())
}

fn sha256_bytes(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    format!("{:x}", hasher.finalize())
}

fn random_nonce_hex() -> Result<String, String> {
    let mut bytes = [0u8; 16];
    getrandom(&mut bytes).map_err(|error| format!("failed to generate nonce: {error}"))?;
    Ok(bytes.iter().map(|value| format!("{value:02x}")).collect::<String>())
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
            value.trim().trim_matches('"').trim_matches('\'').to_string(),
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

fn connection_configs_dir() -> Result<PathBuf, String> {
    let dir = std::env::temp_dir().join("xenage-gui").join("cluster-connections");
    fs::create_dir_all(&dir).map_err(|error| error.to_string())?;
    Ok(dir)
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
        && trimmed
            .chars()
            .skip(1)
            .all(|ch| ch.is_ascii_hexdigit());
    if valid {
        trimmed.to_ascii_lowercase()
    } else {
        "#22c55e".to_string()
    }
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
        .map(|ch| if ch.is_ascii_alphanumeric() { ch.to_ascii_lowercase() } else { '-' })
        .collect();
    slug.trim_matches('-').to_string()
}

fn normalize_archive_path(path: &Path) -> Result<PathBuf, String> {
    if path.is_absolute() {
        return Err("Archive contains an absolute path entry".to_string());
    }

    let mut clean = PathBuf::new();
    for component in path.components() {
        match component {
            std::path::Component::Normal(part) => clean.push(part),
            std::path::Component::CurDir => {}
            _ => {
                return Err(format!(
                    "Archive contains an unsupported path component: {}",
                    path.display()
                ))
            }
        }
    }

    Ok(clean)
}

fn extract_zip(bytes: &[u8], destination: &Path) -> Result<(), String> {
    let reader = Cursor::new(bytes);
    let mut archive = zip::ZipArchive::new(reader).map_err(|error| error.to_string())?;

    for index in 0..archive.len() {
        let mut entry = archive.by_index(index).map_err(|error| error.to_string())?;
        let name = entry
            .enclosed_name()
            .ok_or_else(|| "Zip archive contains an invalid path".to_string())?;
        let clean_name = normalize_archive_path(&name)?;
        let output_path = destination.join(clean_name);

        if entry.is_dir() {
            fs::create_dir_all(&output_path).map_err(|error| error.to_string())?;
            continue;
        }

        if let Some(parent) = output_path.parent() {
            fs::create_dir_all(parent).map_err(|error| error.to_string())?;
        }

        let mut output = fs::File::create(&output_path).map_err(|error| error.to_string())?;
        std::io::copy(&mut entry, &mut output).map_err(|error| error.to_string())?;
    }

    Ok(())
}

fn extract_tar_gz(bytes: &[u8], destination: &Path) -> Result<(), String> {
    let reader = Cursor::new(bytes);
    let gzip = GzDecoder::new(reader);
    let mut archive = tar::Archive::new(gzip);
    let entries = archive.entries().map_err(|error| error.to_string())?;

    for entry_result in entries {
        let mut entry = entry_result.map_err(|error| error.to_string())?;
        let entry_path = entry.path().map_err(|error| error.to_string())?;
        let clean_name = normalize_archive_path(&entry_path)?;
        let output_path = destination.join(clean_name);

        if let Some(parent) = output_path.parent() {
            fs::create_dir_all(parent).map_err(|error| error.to_string())?;
        }

        entry.unpack(&output_path).map_err(|error| error.to_string())?;
    }

    Ok(())
}

#[cfg(unix)]
fn mark_executable(path: &Path) -> Result<(), String> {
    use std::os::unix::fs::PermissionsExt;

    let mut permissions = fs::metadata(path)
        .map_err(|error| error.to_string())?
        .permissions();
    permissions.set_mode(0o755);
    fs::set_permissions(path, permissions).map_err(|error| error.to_string())
}

#[cfg(not(unix))]
fn mark_executable(_path: &Path) -> Result<(), String> {
    Ok(())
}

fn run_command(program: &str, args: &[String]) -> Result<String, String> {
    let output = Command::new(program)
        .args(args)
        .output()
        .map_err(|error| format!("Failed to run {program}: {error}"))?;

    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();

    if output.status.success() {
        if stdout.is_empty() {
            Ok(stderr)
        } else {
            Ok(stdout)
        }
    } else {
        let reason = if !stderr.is_empty() { stderr } else { stdout };
        Err(format!("{program} failed: {reason}"))
    }
}

fn run_command_allow_failure(program: &str, args: &[String]) {
    let _ = Command::new(program).args(args).output();
}

fn service_state_unknown(message: &str) -> ServiceStatus {
    ServiceStatus {
        state: "unknown".to_string(),
        details: Some(message.to_string()),
    }
}

fn quote_systemd_arg(value: &str) -> String {
    format!("\"{}\"", value.replace('\\', "\\\\").replace('"', "\\\""))
}

fn xml_escape(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&apos;")
}

fn home_dir() -> Result<PathBuf, String> {
    std::env::var("HOME")
        .map(PathBuf::from)
        .map_err(|_| "HOME environment variable is not defined".to_string())
}

fn current_uid() -> Result<String, String> {
    if let Ok(uid) = std::env::var("UID") {
        if !uid.is_empty() {
            return Ok(uid);
        }
    }

    let output = run_command("id", &["-u".to_string()])?;
    Ok(output.trim().to_string())
}

fn install_service_linux(role: &NodeRole, binary: &Path, args: &[String]) -> Result<String, String> {
    let unit_name = format!("xenage-{}.service", role.service_slug());
    let unit_dir = home_dir()?.join(".config/systemd/user");
    fs::create_dir_all(&unit_dir).map_err(|error| error.to_string())?;

    let unit_path = unit_dir.join(&unit_name);
    let exec_args = std::iter::once(binary.to_string_lossy().to_string())
        .chain(args.iter().cloned())
        .map(|value| quote_systemd_arg(&value))
        .collect::<Vec<_>>()
        .join(" ");

    let content = format!(
        "[Unit]\nDescription=Xenage {}\nAfter=network.target\n\n[Service]\nType=simple\nExecStart={}\nRestart=always\nRestartSec=3\n\n[Install]\nWantedBy=default.target\n",
        role.service_title(), exec_args
    );
    fs::write(&unit_path, content).map_err(|error| error.to_string())?;

    run_command("systemctl", &["--user".to_string(), "daemon-reload".to_string()])?;
    run_command(
        "systemctl",
        &[
            "--user".to_string(),
            "enable".to_string(),
            unit_name.clone(),
        ],
    )?;

    Ok(format!("Installed user systemd service: {}", unit_path.display()))
}

fn start_service_linux(role: &NodeRole) -> Result<String, String> {
    let unit_name = format!("xenage-{}.service", role.service_slug());
    run_command(
        "systemctl",
        &["--user".to_string(), "start".to_string(), unit_name.clone()],
    )?;
    Ok(format!("Started {unit_name}"))
}

fn stop_service_linux(role: &NodeRole) -> Result<String, String> {
    let unit_name = format!("xenage-{}.service", role.service_slug());
    run_command(
        "systemctl",
        &["--user".to_string(), "stop".to_string(), unit_name.clone()],
    )?;
    Ok(format!("Stopped {unit_name}"))
}

fn service_status_linux(role: &NodeRole) -> ServiceStatus {
    let unit_name = format!("xenage-{}.service", role.service_slug());
    let unit_path = match home_dir() {
        Ok(home) => home.join(".config/systemd/user").join(&unit_name),
        Err(error) => return service_state_unknown(&error),
    };

    if !unit_path.exists() {
        return ServiceStatus {
            state: "not-installed".to_string(),
            details: Some(format!("{} is missing", unit_path.display())),
        };
    }

    match run_command(
        "systemctl",
        &[
            "--user".to_string(),
            "is-active".to_string(),
            unit_name.clone(),
        ],
    ) {
        Ok(output) => ServiceStatus {
            state: output.trim().to_string(),
            details: Some(unit_name),
        },
        Err(error) => ServiceStatus {
            state: "stopped".to_string(),
            details: Some(error),
        },
    }
}

fn plist_path(role: &NodeRole) -> Result<PathBuf, String> {
    Ok(home_dir()?
        .join("Library/LaunchAgents")
        .join(format!("com.xenage.{}.plist", role.service_slug())))
}

fn launchctl_target(role: &NodeRole) -> Result<String, String> {
    let uid = current_uid()?;
    Ok(format!("gui/{uid}/com.xenage.{}", role.service_slug()))
}

fn install_service_macos(role: &NodeRole, binary: &Path, args: &[String]) -> Result<String, String> {
    let plist = plist_path(role)?;
    if let Some(parent) = plist.parent() {
        fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    }

    let program_args = std::iter::once(binary.to_string_lossy().to_string())
        .chain(args.iter().cloned())
        .map(|value| format!("    <string>{}</string>", xml_escape(&value)))
        .collect::<Vec<_>>()
        .join("\n");

    let content = format!(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">\n<plist version=\"1.0\">\n<dict>\n  <key>Label</key>\n  <string>com.xenage.{slug}</string>\n  <key>ProgramArguments</key>\n  <array>\n{program_args}\n  </array>\n  <key>RunAtLoad</key>\n  <true/>\n  <key>KeepAlive</key>\n  <true/>\n  <key>StandardOutPath</key>\n  <string>{stdout}</string>\n  <key>StandardErrorPath</key>\n  <string>{stderr}</string>\n</dict>\n</plist>\n",
        slug = role.service_slug(),
        program_args = program_args,
        stdout = xml_escape(&home_dir()?.join(format!(".xenage-{}.out.log", role.service_slug())).display().to_string()),
        stderr = xml_escape(&home_dir()?.join(format!(".xenage-{}.err.log", role.service_slug())).display().to_string())
    );

    fs::write(&plist, content).map_err(|error| error.to_string())?;

    let target = launchctl_target(role)?;
    run_command_allow_failure(
        "launchctl",
        &[
            "bootout".to_string(),
            target.clone(),
            plist.display().to_string(),
        ],
    );
    run_command(
        "launchctl",
        &[
            "bootstrap".to_string(),
            format!("gui/{}", current_uid()?),
            plist.display().to_string(),
        ],
    )?;

    Ok(format!("Installed launchd agent: {} ({target})", plist.display()))
}

fn start_service_macos(role: &NodeRole) -> Result<String, String> {
    let target = launchctl_target(role)?;
    run_command(
        "launchctl",
        &["kickstart".to_string(), "-k".to_string(), target.clone()],
    )?;
    Ok(format!("Started {target}"))
}

fn stop_service_macos(role: &NodeRole) -> Result<String, String> {
    let target = launchctl_target(role)?;
    let plist = plist_path(role)?;
    run_command(
        "launchctl",
        &[
            "bootout".to_string(),
            target.clone(),
            plist.display().to_string(),
        ],
    )?;
    Ok(format!("Stopped {target}"))
}

fn service_status_macos(role: &NodeRole) -> ServiceStatus {
    let plist = match plist_path(role) {
        Ok(path) => path,
        Err(error) => return service_state_unknown(&error),
    };

    if !plist.exists() {
        return ServiceStatus {
            state: "not-installed".to_string(),
            details: Some(format!("{} is missing", plist.display())),
        };
    }

    let target = match launchctl_target(role) {
        Ok(value) => value,
        Err(error) => return service_state_unknown(&error),
    };

    match run_command("launchctl", &["print".to_string(), target.clone()]) {
        Ok(output) => {
            let state = if output.contains("state = running") {
                "running"
            } else {
                "loaded"
            };
            ServiceStatus {
                state: state.to_string(),
                details: Some(target),
            }
        }
        Err(error) => ServiceStatus {
            state: "stopped".to_string(),
            details: Some(error),
        },
    }
}

fn windows_service_name(role: &NodeRole) -> String {
    format!("Xenage{}", role.service_title().replace(' ', ""))
}

fn install_service_windows(role: &NodeRole, binary: &Path, args: &[String]) -> Result<String, String> {
    let service_name = windows_service_name(role);
    let mut binary_command = format!("\"{}\"", binary.display());
    for arg in args {
        binary_command.push(' ');
        if arg.contains(' ') {
            binary_command.push('"');
            binary_command.push_str(&arg.replace('"', "\\\""));
            binary_command.push('"');
        } else {
            binary_command.push_str(arg);
        }
    }

    run_command_allow_failure(
        "sc.exe",
        &[
            "stop".to_string(),
            service_name.clone(),
        ],
    );
    run_command_allow_failure(
        "sc.exe",
        &[
            "delete".to_string(),
            service_name.clone(),
        ],
    );

    run_command(
        "sc.exe",
        &[
            "create".to_string(),
            service_name.clone(),
            "binPath=".to_string(),
            binary_command,
            "start=".to_string(),
            "auto".to_string(),
        ],
    )?;

    Ok(format!("Installed Windows service: {service_name}"))
}

fn start_service_windows(role: &NodeRole) -> Result<String, String> {
    let service_name = windows_service_name(role);
    run_command("sc.exe", &["start".to_string(), service_name.clone()])?;
    Ok(format!("Started {service_name}"))
}

fn stop_service_windows(role: &NodeRole) -> Result<String, String> {
    let service_name = windows_service_name(role);
    run_command("sc.exe", &["stop".to_string(), service_name.clone()])?;
    Ok(format!("Stopped {service_name}"))
}

fn service_status_windows(role: &NodeRole) -> ServiceStatus {
    let service_name = windows_service_name(role);
    match run_command("sc.exe", &["query".to_string(), service_name.clone()]) {
        Ok(output) => {
            let upper = output.to_ascii_uppercase();
            let state = if upper.contains("RUNNING") {
                "running"
            } else if upper.contains("STOPPED") {
                "stopped"
            } else {
                "unknown"
            };
            ServiceStatus {
                state: state.to_string(),
                details: Some(service_name),
            }
        }
        Err(error) => {
            if error.contains("1060") || error.to_ascii_lowercase().contains("does not exist") {
                ServiceStatus {
                    state: "not-installed".to_string(),
                    details: Some(service_name),
                }
            } else {
                ServiceStatus {
                    state: "unknown".to_string(),
                    details: Some(error),
                }
            }
        }
    }
}

fn install_service_for_role(app: &AppHandle, role: &NodeRole, args: &[String]) -> Result<String, String> {
    if args.is_empty() {
        return Err(format!(
            "No command arguments were provided for {}",
            role.binary_name()
        ));
    }

    let binary = installed_binary_path(app, role)?;

    match std::env::consts::OS {
        "linux" => install_service_linux(role, &binary, args),
        "macos" => install_service_macos(role, &binary, args),
        "windows" => install_service_windows(role, &binary, args),
        os => Err(format!("Service installation is unsupported on OS: {os}")),
    }
}

fn start_service_for_role(role: &NodeRole) -> Result<String, String> {
    match std::env::consts::OS {
        "linux" => start_service_linux(role),
        "macos" => start_service_macos(role),
        "windows" => start_service_windows(role),
        os => Err(format!("Service start is unsupported on OS: {os}")),
    }
}

fn stop_service_for_role(role: &NodeRole) -> Result<String, String> {
    match std::env::consts::OS {
        "linux" => stop_service_linux(role),
        "macos" => stop_service_macos(role),
        "windows" => stop_service_windows(role),
        os => Err(format!("Service stop is unsupported on OS: {os}")),
    }
}

fn service_status_for_role(role: &NodeRole) -> ServiceStatus {
    match std::env::consts::OS {
        "linux" => service_status_linux(role),
        "macos" => service_status_macos(role),
        "windows" => service_status_windows(role),
        os => service_state_unknown(&format!("Service status unsupported on OS: {os}")),
    }
}

fn read_manifest_version(app: &AppHandle) -> Option<String> {
    let manifest = manifest_path(app).ok()?;
    let content = fs::read_to_string(manifest).ok()?;
    let manifest: StandaloneManifest = serde_json::from_str(&content).ok()?;
    Some(manifest.version)
}

#[tauri::command]
async fn check_for_updates(
    app: AppHandle,
    channel: Option<String>,
    force: Option<bool>,
) -> Result<Option<UpdateMetadata>, String> {
    let channel = channel.unwrap_or_else(|| "main".to_string());
    let update = fetch_update(&app, &channel, force.unwrap_or(false)).await?;

    Ok(update.map(|update| UpdateMetadata {
        current_version: update.current_version,
        version: update.version,
        notes: update.body,
        pub_date: update.date.map(|date| date.to_string()),
        target: update.target,
    }))
}

#[tauri::command]
async fn install_update(
    app: AppHandle,
    channel: Option<String>,
    force: Option<bool>,
) -> Result<bool, String> {
    let channel = channel.unwrap_or_else(|| "main".to_string());

    if let Some(update) = fetch_update(&app, &channel, force.unwrap_or(false)).await? {
        let endpoint = update_endpoint(&channel).to_string();
        let force = force.unwrap_or(false);
        let mut downloaded_bytes = 0usize;
        let app_handle = app.clone();
        let progress_channel = channel.clone();
        let progress_endpoint = endpoint.clone();

        emit_update_log(
            &app,
            UpdateLogEvent {
                channel: channel.clone(),
                endpoint: endpoint.clone(),
                step: "download-started".into(),
                message: format!("Downloading update {} for target {}", update.version, update.target),
                force,
                current_version: Some(update.current_version.clone()),
                version: Some(update.version.clone()),
                target: Some(update.target.clone()),
                downloaded_bytes: Some(0),
                content_length: None,
            },
        );

        update
            .download_and_install(
                move |chunk_length, content_length| {
                    downloaded_bytes += chunk_length;
                    emit_update_log(
                        &app_handle,
                        UpdateLogEvent {
                            channel: progress_channel.clone(),
                            endpoint: progress_endpoint.clone(),
                            step: "download-progress".into(),
                            message: format!(
                                "Downloaded {} bytes{}",
                                downloaded_bytes,
                                content_length
                                    .map(|total| format!(" of {total}"))
                                    .unwrap_or_default()
                            ),
                            force,
                            current_version: None,
                            version: None,
                            target: None,
                            downloaded_bytes: Some(downloaded_bytes),
                            content_length,
                        },
                    );
                },
                {
                    let app_handle = app.clone();
                    let channel = channel.clone();
                    let endpoint = endpoint.clone();
                    move || {
                        emit_update_log(
                            &app_handle,
                            UpdateLogEvent {
                                channel: channel.clone(),
                                endpoint: endpoint.clone(),
                                step: "download-finished".into(),
                                message: "Download finished, installing update".into(),
                                force,
                                current_version: None,
                                version: None,
                                target: None,
                                downloaded_bytes: None,
                                content_length: None,
                            },
                        );
                    }
                },
            )
            .await
            .map_err(|error| error.to_string())?;

        emit_update_log(
            &app,
            UpdateLogEvent {
                channel,
                endpoint,
                step: "install-finished".into(),
                message: "Update installed successfully".into(),
                force,
                current_version: None,
                version: None,
                target: None,
                downloaded_bytes: None,
                content_length: None,
            },
        );

        Ok(true)
    } else {
        Ok(false)
    }
}

#[tauri::command]
async fn install_standalone_bundle(
    app: AppHandle,
    channel: Option<String>,
) -> Result<StandaloneInstallResult, String> {
    let channel = channel.unwrap_or_else(|| "main".to_string());
    let asset_name = standalone_asset_name()?;
    let base_url = standalone_base_endpoint(&channel);
    let asset_url = format!("{base_url}/{asset_name}");
    let checksum_url = format!("{asset_url}.sha256");

    emit_standalone_log(
        &app,
        StandaloneLogEvent {
            channel: channel.clone(),
            asset: asset_name.clone(),
            step: "download-started".to_string(),
            message: format!("Downloading standalone bundle from {asset_url}"),
        },
    );

    let client = reqwest::Client::new();
    let archive_bytes = client
        .get(&asset_url)
        .send()
        .await
        .map_err(|error| error.to_string())?
        .error_for_status()
        .map_err(|error| error.to_string())?
        .bytes()
        .await
        .map_err(|error| error.to_string())?;

    let checksum_payload = client
        .get(&checksum_url)
        .send()
        .await
        .map_err(|error| error.to_string())?
        .error_for_status()
        .map_err(|error| error.to_string())?
        .text()
        .await
        .map_err(|error| error.to_string())?;

    let expected_checksum = parse_checksum(&checksum_payload)?;
    let actual_checksum = sha256_bytes(archive_bytes.as_ref());
    if expected_checksum != actual_checksum {
        return Err(format!(
            "Checksum mismatch for {asset_name}: expected {expected_checksum}, got {actual_checksum}"
        ));
    }

    let root = standalone_root(&app)?;
    let temp_extract = root.join("extract");
    if temp_extract.exists() {
        fs::remove_dir_all(&temp_extract).map_err(|error| error.to_string())?;
    }
    fs::create_dir_all(&temp_extract).map_err(|error| error.to_string())?;

    if asset_name.ends_with(".zip") {
        extract_zip(archive_bytes.as_ref(), &temp_extract)?;
    } else {
        extract_tar_gz(archive_bytes.as_ref(), &temp_extract)?;
    }

    let bin_dir = standalone_bin_dir(&app)?;
    let cp_source = temp_extract.join(if std::env::consts::OS == "windows" {
        "xenage-control-plane.exe"
    } else {
        "xenage-control-plane"
    });
    let rt_source = temp_extract.join(if std::env::consts::OS == "windows" {
        "xenage-runtime.exe"
    } else {
        "xenage-runtime"
    });

    if !cp_source.exists() || !rt_source.exists() {
        return Err("Standalone archive is missing required binaries".to_string());
    }

    let cp_target = bin_dir.join(cp_source.file_name().unwrap_or_default());
    let rt_target = bin_dir.join(rt_source.file_name().unwrap_or_default());

    fs::copy(&cp_source, &cp_target).map_err(|error| error.to_string())?;
    fs::copy(&rt_source, &rt_target).map_err(|error| error.to_string())?;
    mark_executable(&cp_target)?;
    mark_executable(&rt_target)?;

    let manifest_source = temp_extract.join("standalone-manifest.json");
    let manifest_destination = manifest_path(&app)?;
    if manifest_source.exists() {
        fs::copy(&manifest_source, &manifest_destination).map_err(|error| error.to_string())?;
    } else {
        let fallback = serde_json::json!({
            "version": "unknown",
            "asset": asset_name,
        });
        fs::write(
            &manifest_destination,
            serde_json::to_string_pretty(&fallback).map_err(|error| error.to_string())?,
        )
        .map_err(|error| error.to_string())?;
    }

    let version = read_manifest_version(&app).unwrap_or_else(|| "unknown".to_string());

    emit_standalone_log(
        &app,
        StandaloneLogEvent {
            channel,
            asset: asset_name.clone(),
            step: "install-finished".to_string(),
            message: format!("Standalone binaries installed to {}", bin_dir.display()),
        },
    );

    Ok(StandaloneInstallResult {
        version,
        install_dir: bin_dir.display().to_string(),
        asset_name,
    })
}

#[tauri::command]
async fn install_node_service(
    app: AppHandle,
    role: String,
    args: Vec<String>,
) -> Result<String, String> {
    let role = NodeRole::parse(&role)?;
    install_service_for_role(&app, &role, &args)
}

#[tauri::command]
async fn start_node_service(role: String) -> Result<String, String> {
    let role = NodeRole::parse(&role)?;
    start_service_for_role(&role)
}

#[tauri::command]
async fn stop_node_service(role: String) -> Result<String, String> {
    let role = NodeRole::parse(&role)?;
    stop_service_for_role(&role)
}

#[tauri::command]
async fn standalone_status(app: AppHandle) -> Result<StandaloneStatus, String> {
    let bin_dir = standalone_bin_dir(&app)?;
    let asset_name = standalone_asset_name()?;
    let cp = NodeRole::ControlPlane;
    let rt = NodeRole::Runtime;
    let cp_exists = installed_binary_path(&app, &cp).is_ok();
    let rt_exists = installed_binary_path(&app, &rt).is_ok();

    Ok(StandaloneStatus {
        installed: cp_exists && rt_exists,
        install_dir: bin_dir.display().to_string(),
        asset_name,
        version: read_manifest_version(&app),
        control_plane_service: service_status_for_role(&cp),
        runtime_service: service_status_for_role(&rt),
    })
}

#[tauri::command]
async fn fetch_cluster_snapshot_from_yaml(config_yaml: String) -> Result<serde_json::Value, String> {
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

    let client = reqwest::Client::builder()
        .use_rustls_tls()
        .build()
        .map_err(|error| error.to_string())?;
    let mut errors: Vec<String> = vec![];
    for base in &config.control_plane_urls {
        let url = format!("{}{}", base.trim_end_matches('/'), path);
        let response = match client
            .get(&url)
            .header("x-node-id", &config.user_id)
            .header("x-timestamp", timestamp.to_string())
            .header("x-nonce", &nonce)
            .header("x-signature", &signature_b64)
            .header("x-public-key", &config.public_key)
            .send()
            .await
        {
            Ok(value) => value,
            Err(error) => {
                errors.push(format!("{url}: {error}"));
                continue;
            }
        };
        let status = response.status();
        let body = response.text().await.map_err(|error| error.to_string())?;
        if status.is_success() {
            return serde_json::from_str(&body)
                .map_err(|error| format!("invalid control-plane response: {error}"));
        }
        errors.push(format!("{url}: control-plane rejected request ({status}): {body}"));
    }
    Err(errors.join(" | "))
}

#[tauri::command]
async fn save_cluster_connection_yaml(config_yaml: String) -> Result<StoredClusterConnection, String> {
    let config = parse_gui_connection_yaml(&config_yaml)?;
    let dir = connection_configs_dir()?;
    let base_name = format!("{}-{}", safe_slug(&config.cluster_name), safe_slug(&config.user_id));
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

#[tauri::command]
async fn list_cluster_connection_yamls() -> Result<Vec<StoredClusterConnection>, String> {
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

#[tauri::command]
async fn list_cluster_ui_prefs() -> Result<Vec<ClusterUiPrefsEntry>, String> {
    load_cluster_ui_prefs_file()
}

#[tauri::command]
async fn save_cluster_ui_prefs_entry(
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

#[tauri::command]
async fn delete_cluster_connection(connection_id: String) -> Result<(), String> {
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

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_process::init())
        .invoke_handler(tauri::generate_handler![
            check_for_updates,
            install_update,
            install_standalone_bundle,
            install_node_service,
            start_node_service,
            stop_node_service,
            standalone_status,
            fetch_cluster_snapshot_from_yaml,
            save_cluster_connection_yaml,
            list_cluster_connection_yamls,
            list_cluster_ui_prefs,
            save_cluster_ui_prefs_entry,
            delete_cluster_connection
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
