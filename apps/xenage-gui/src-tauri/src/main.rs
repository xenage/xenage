// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Serialize;
use tauri::AppHandle;
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

fn update_endpoint(channel: &str) -> &'static str {
    match channel {
        "dev" => DEV_UPDATE_ENDPOINT,
        _ => STABLE_UPDATE_ENDPOINT,
    }
}

async fn fetch_update(
    app: &AppHandle,
    channel: &str,
    force: bool,
) -> Result<Option<tauri_plugin_updater::Update>, String> {
    let endpoint = Url::parse(update_endpoint(channel)).map_err(|error| error.to_string())?;

    let mut builder = app
        .updater_builder()
        .endpoints(vec![endpoint])
        .map_err(|error| error.to_string())?;

    if force {
        builder = builder.version_comparator(|_, _| true);
    }

    let updater = builder.build().map_err(|error| error.to_string())?;
    updater.check().await.map_err(|error| error.to_string())
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
        update
            .download_and_install(
                |_chunk_length, _content_length| {},
                || {},
            )
            .await
            .map_err(|error| error.to_string())?;

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
