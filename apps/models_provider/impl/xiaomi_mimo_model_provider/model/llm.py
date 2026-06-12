# coding=utf-8
from typing import Dict

from models_provider.base_model_provider import MaxKBBaseModel
from models_provider.impl.base_chat_open_ai import BaseChatOpenAI

XIAOMI_MIMO_API_BASE = 'https://api.mimo.xiaomi.com/v1'


class XiaomiMiMoChatModel(MaxKBBaseModel, BaseChatOpenAI):
    @staticmethod
    def is_cache_model():
        return False

    @staticmethod
    def new_instance(model_type, model_name, model_credential: Dict[str, object], **model_kwargs):
        optional_params = MaxKBBaseModel.filter_optional_params(model_kwargs)
        return XiaomiMiMoChatModel(
            openai_api_base=XIAOMI_MIMO_API_BASE,
            openai_api_key=model_credential['api_key'],
            model=model_name,
            **optional_params,
        )
