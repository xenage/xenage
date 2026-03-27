# Simple Integration Test

## What it does

- `docker-compose` starts 5 raw containers (`3 control-plane + 2 runtime`) with no auto setup.
- Bash script bootstraps the cluster via CLI commands.
- Creates GUI admin connection config.
- Verifies CLI and GUI client connectivity.
- Simulates leader failure and verifies leader switch.
- Verifies the new leader has the expected admin user/public key.

## Run

```bash
./integration_test/simple/test_simple_cluster.sh
```

The script always builds `xenage:local` and stores runtime artifacts in `integration_test/simple/artifacts`.
