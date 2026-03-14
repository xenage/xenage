// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Serialize;
use tauri::{AppHandle, Emitter};
use tauri_plugin_updater::UpdaterExt;
use url::Url;

const STABLE_UPDATE_ENDPOINT: &str =
    "https://github.com/xenage/xenage/releases/latest/download/latest.json";
const DEV_UPDATE_ENDPOINT: &str =
    "https://github.com/xenage/xenage/releases/download/xenage-gui-dev/latest.json";

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

fn update_endpoint(channel: &str) -> &'static str {
    match channel {
        "dev" => DEV_UPDATE_ENDPOINT,
        _ => STABLE_UPDATE_ENDPOINT,
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

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_process::init())
        .invoke_handler(tauri::generate_handler![check_for_updates, install_update])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
