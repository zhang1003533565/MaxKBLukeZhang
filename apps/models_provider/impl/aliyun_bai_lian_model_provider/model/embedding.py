# coding=utf-8
"""
    @project: MaxKB
    @Author：虎
    @file： embedding.py
    @date：2024/10/16 16:34
    @desc:
"""
from http import HTTPStatus
from typing import Any, Dict, List

from openai import OpenAI

from models_provider.base_model_provider import MaxKBBaseModel

IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".ico")
VIDEO_SUFFIXES = (".mp4", ".avi", ".mov", ".mpeg", ".mpg", ".webm", ".flv", ".mkv")
BAILIAN_EMBEDDING_API_BASE = 'https://dashscope.aliyuncs.com/compatible-mode/v1'


class AliyunBaiLianEmbedding(MaxKBBaseModel):
    model_name: str
    optional_params: dict
    api_base: str
    api_key: str

    def __init__(self, api_key, model_name: str, api_base: str, optional_params: dict):
        self.client = OpenAI(api_key=api_key, base_url=api_base).embeddings
        self.model_name = model_name
        self.optional_params = optional_params
        self.api_key = api_key
        self.api_base = api_base

    def is_cache_model(self):
        return False

    @staticmethod
    def new_instance(model_type, model_name, model_credential: Dict[str, object], **model_kwargs):
        optional_params = MaxKBBaseModel.filter_optional_params(model_kwargs)
        return AliyunBaiLianEmbedding(
            api_key=model_credential.get('dashscope_api_key'),
            model_name=model_name,
            api_base=BAILIAN_EMBEDDING_API_BASE,
            optional_params=optional_params
        )

    def embed_query(self, text: str):
        res = self.embed_documents([text])
        return res[0]

    @staticmethod
    def _looks_like_media_url(value: str, suffixes: tuple[str, ...]):
        lower_value = value.lower().split("?", 1)[0]
        return lower_value.startswith(("http://", "https://")) and lower_value.endswith(suffixes)

    @staticmethod
    def _to_multimodal_content(value: Any):
        if isinstance(value, dict):
            return value
        if isinstance(value, (list, tuple)):
            return {"multi_images": list(value)}
        text = str(value)
        if text.startswith("data:image/") or AliyunBaiLianEmbedding._looks_like_media_url(text, IMAGE_SUFFIXES):
            return {"image": text}
        if text.startswith("data:video/") or AliyunBaiLianEmbedding._looks_like_media_url(text, VIDEO_SUFFIXES):
            return {"video": text}
        return {"text": text}

    def _is_multimodal_model(self):
        return any(k in self.model_name for k in ("vl-embedding", "embedding-vision", "multimodal"))

    def _dashscope_api_base(self):
        if "compatible-mode" in self.api_base:
            return "https://dashscope.aliyuncs.com/api/v1"
        return self.api_base or "https://dashscope.aliyuncs.com/api/v1"

    def _multimodal_optional_params(self):
        params = dict(self.optional_params)
        if "dimensions" in params and "dimension" not in params:
            params["dimension"] = params.pop("dimensions")
        if "dimension" in params:
            params["dimension"] = int(params["dimension"])
        if self.model_name != "qwen3-vl-embedding" or not params.get("enable_fusion"):
            params.pop("enable_fusion", None)
        return params

    def _text_optional_params(self):
        params = dict(self.optional_params)
        params.pop("enable_fusion", None)
        return params

    def embed_documents(
            self, texts: List[Any], chunk_size: int | None = None
    ) -> List[List[float]]:
        # 处理多模态的向量化
        if self._is_multimodal_model():
            import dashscope
            dashscope.api_key = self.api_key
            dashscope.base_http_api_url = self._dashscope_api_base()
            resp = dashscope.MultiModalEmbedding.call(
                model=self.model_name,
                input={"contents": [self._to_multimodal_content(text) for text in texts]},  # type: ignore
                **self._multimodal_optional_params()
            )

            if resp.status_code == HTTPStatus.OK:
                embeddings_data = resp.output.get('embeddings', [])
                return [item.get('embedding', []) for item in embeddings_data]
            else:
                raise Exception(f'MultiModalEmbedding call failed: status={resp.status_code}, message={resp.message}')

        text_optional_params = self._text_optional_params()
        if len(text_optional_params) > 0:
            res = self.client.create(
                input=texts, model=self.model_name, encoding_format="float",
                **text_optional_params
            )
        else:
            res = self.client.create(input=texts, model=self.model_name, encoding_format="float")
        return [e.embedding for e in res.data]
