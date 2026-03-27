from __future__ import annotations

from ..base import Structure
from ..common import ObjectMeta


class ResourceDocument(Structure, kw_only=True, omit_defaults=True):
    metadata: ObjectMeta
    apiVersion: str = "xenage.io/v1alpha1"
