from typing import Literal, cast

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, SecretStr

from byod.config import Config, Selection
from byod.db.migrations import connect
from byod.index.store import stale_index
from byod.llm.base import ProviderError
from byod.llm.keys import KeyStore
from byod.llm.providers import ProviderFactory
from byod.model_files import MODEL_NAME, MODEL_VERSION

router = APIRouter(prefix="/api/settings")
ProviderName = Literal["openai", "anthropic", "ollama"]


class SettingsInput(BaseModel):
    provider: ProviderName | None = None
    model: str | None = Field(default=None, max_length=200)
    workspace_id: int | None = None
    retrieval_min_score: float | None = Field(default=None, ge=0, le=1)


class KeyInput(BaseModel):
    provider: Literal["openai", "anthropic"]
    key: SecretStr = Field(min_length=1, max_length=4096)


def require_workspace(config: Config, workspace_id: int | None) -> None:
    if workspace_id is not None:
        with connect(config) as db:
            if not db.execute("SELECT 1 FROM workspaces WHERE id=?", (workspace_id,)).fetchone():
                raise HTTPException(404, "Workspace not found. Select another workspace.")


@router.get("")
def settings(request: Request, workspace_id: int | None = None) -> dict[str, object]:
    config = cast(Config, request.app.state.config)
    keys = cast(KeyStore, request.app.state.keys)
    factory = cast(ProviderFactory, request.app.state.provider_factory)
    require_workspace(config, workspace_id)
    preferences = config.preferences()
    active = preferences.selection(workspace_id)
    providers = []
    for name in ("openai", "anthropic", "ollama"):
        configured = keys.configured(name) if name != "ollama" else False
        try:
            # Only the selected configured cloud provider may receive model queries.
            key = keys.get(name) if configured and active.provider == name else None
            models = factory(name, key).list_models()
        except ProviderError:
            models = []
        providers.append(
            {
                "name": name,
                "available": bool(models) if name == "ollama" else True,
                "configured": bool(models) if name == "ollama" else configured,
                "models": models,
            }
        )
    with connect(config) as db:
        stale = stale_index(db, workspace_id)
    return {
        "providers": providers,
        "active": active.model_dump(),
        "embed_model": MODEL_NAME,
        "embed_version": MODEL_VERSION,
        "stale_index": stale,
        "retrieval_min_score": preferences.retrieval_min_score,
        "data_dir": str(config.data_dir),
    }


@router.put("")
def save_settings(body: SettingsInput, request: Request) -> dict[str, bool]:
    config = cast(Config, request.app.state.config)
    require_workspace(config, body.workspace_id)
    preferences = config.preferences()
    current = preferences.selection(body.workspace_id)
    provider_name = body.provider or current.provider
    selected = None
    if body.provider is not None or body.model is not None:
        if provider_name is None:
            raise HTTPException(422, "Select a provider before choosing a model.")
        keys = cast(KeyStore, request.app.state.keys)
        factory = cast(ProviderFactory, request.app.state.provider_factory)
        key = keys.get(provider_name) if keys.configured(provider_name) else None
        models = factory(provider_name, key).list_models()
        model = body.model or (current.model if current.provider == provider_name else "")
        if not model and models:
            model = models[0]
        if not model or model not in models:
            raise HTTPException(422, "Model unavailable. Choose a listed model in Settings.")
        selected = Selection(provider=provider_name, model=model)
    with config.edit_preferences() as updated:
        if selected is not None:
            if body.workspace_id is None:
                updated.active = selected
            else:
                updated.workspaces[str(body.workspace_id)] = selected
        if body.retrieval_min_score is not None:
            updated.retrieval_min_score = body.retrieval_min_score
    return {"saved": True}


@router.put("/key")
def save_key(body: KeyInput, request: Request) -> dict[str, bool]:
    factory = cast(ProviderFactory, request.app.state.provider_factory)
    secret = body.key.get_secret_value()
    if not factory(body.provider, secret).validate():
        return {"valid": False}
    cast(KeyStore, request.app.state.keys).set(body.provider, secret)
    return {"valid": True}


@router.delete("/key/{provider}", status_code=204)
def delete_key(provider: Literal["openai", "anthropic"], request: Request) -> Response:
    cast(KeyStore, request.app.state.keys).delete(provider)
    return Response(status_code=204)
