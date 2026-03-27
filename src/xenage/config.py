from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dynaconf import Dynaconf
from loguru import logger


@dataclass(frozen=True)
class NetworkConfig:
    control_plane_host: str
    control_plane_port: int
    runtime_host: str
    runtime_port: int


@dataclass(frozen=True)
class ControlPlaneConfig:
    init_ttl_seconds: int
    bootstrap_ttl_seconds: int
    state_ttl_seconds: int
    failover_check_interval_seconds: int
    failover_escalation_seconds: int
    auto_failover: bool


@dataclass(frozen=True)
class RuntimeConfig:
    join_retry_interval_seconds: int


@dataclass(frozen=True)
class AppConfig:
    log_level: str
    network: NetworkConfig
    control_plane: ControlPlaneConfig
    runtime: RuntimeConfig


DEFAULT_CONFIG = AppConfig(
    log_level="INFO",
    network=NetworkConfig(
        control_plane_host="0.0.0.0",
        control_plane_port=8734,
        runtime_host="0.0.0.0",
        runtime_port=8735,
    ),
    control_plane=ControlPlaneConfig(
        init_ttl_seconds=60,
        bootstrap_ttl_seconds=300,
        state_ttl_seconds=5,
        failover_check_interval_seconds=1,
        failover_escalation_seconds=15,
        auto_failover=True,
    ),
    runtime=RuntimeConfig(
        join_retry_interval_seconds=1,
    ),
)


def _build_dynaconf(config_path: Path | None) -> Dynaconf:
    settings_files: list[str] = []
    if config_path is not None:
        settings_files.append(str(config_path))
    logger.debug("loading configuration config_path={} settings_files={}", config_path, settings_files)
    return Dynaconf(
        settings_files=settings_files,
        environments=False,
        envvar_prefix="XENAGE",
        load_dotenv=False,
    )


def load_config(config_path: Path | None) -> AppConfig:
    settings = _build_dynaconf(config_path)
    network = settings.get("network", {})
    control_plane = settings.get("control_plane", {})
    runtime = settings.get("runtime", {})
    config = AppConfig(
        log_level=str(settings.get("log_level", DEFAULT_CONFIG.log_level)),
        network=NetworkConfig(
            control_plane_host=str(network.get("control_plane_host", DEFAULT_CONFIG.network.control_plane_host)),
            control_plane_port=int(network.get("control_plane_port", DEFAULT_CONFIG.network.control_plane_port)),
            runtime_host=str(network.get("runtime_host", DEFAULT_CONFIG.network.runtime_host)),
            runtime_port=int(network.get("runtime_port", DEFAULT_CONFIG.network.runtime_port)),
        ),
        control_plane=ControlPlaneConfig(
            init_ttl_seconds=int(control_plane.get("init_ttl_seconds", DEFAULT_CONFIG.control_plane.init_ttl_seconds)),
            bootstrap_ttl_seconds=int(control_plane.get("bootstrap_ttl_seconds", DEFAULT_CONFIG.control_plane.bootstrap_ttl_seconds)),
            state_ttl_seconds=int(control_plane.get("state_ttl_seconds", DEFAULT_CONFIG.control_plane.state_ttl_seconds)),
            failover_check_interval_seconds=int(
                control_plane.get("failover_check_interval_seconds", DEFAULT_CONFIG.control_plane.failover_check_interval_seconds),
            ),
            failover_escalation_seconds=int(
                control_plane.get("failover_escalation_seconds", DEFAULT_CONFIG.control_plane.failover_escalation_seconds),
            ),
            auto_failover=bool(control_plane.get("auto_failover", DEFAULT_CONFIG.control_plane.auto_failover)),
        ),
        runtime=RuntimeConfig(
            join_retry_interval_seconds=int(runtime.get("join_retry_interval_seconds", DEFAULT_CONFIG.runtime.join_retry_interval_seconds)),
        ),
    )
    logger.debug(
        "configuration loaded log_level={} control_plane={} runtime={}",
        config.log_level,
        config.control_plane,
        config.runtime,
    )
    return config
