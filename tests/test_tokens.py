from __future__ import annotations

import pytest

from xenage.tokens import BootstrapTokenManager, TokenValidationError


def test_bootstrap_token_is_one_time() -> None:
    manager = BootstrapTokenManager()
    record = manager.issue_token(60)
    manager.validate(record.token)
    manager.mark_used(record.token)
    with pytest.raises(TokenValidationError):
        manager.validate(record.token)
