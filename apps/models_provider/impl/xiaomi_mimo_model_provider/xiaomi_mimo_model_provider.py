# coding=utf-8
"""
    @project: MaxKB
    @file：xiaomi_mimo_model_provider.py
    @desc: Xiaomi MiMo model provider.
"""
import os

from common.utils.common import get_file_content
from maxkb.conf import PROJECT_DIR
from models_provider.base_model_provider import (
    IModelProvider,
    ModelInfo,
    ModelInfoManage,
    ModelProvideInfo,
    ModelTypeConst,
)
from models_provider.impl.xiaomi_mimo_model_provider.credential.llm import XiaomiMiMoLLMModelCredential
from models_provider.impl.xiaomi_mimo_model_provider.model.llm import XiaomiMiMoChatModel

xiaomi_mimo_llm_model_credential = XiaomiMiMoLLMModelCredential()

xiaomi_mimo_llm_list = [
    ModelInfo("MiMo-V2.5-Pro", "", ModelTypeConst.LLM, xiaomi_mimo_llm_model_credential, XiaomiMiMoChatModel),
    ModelInfo("MiMo-V2.5", "", ModelTypeConst.LLM, xiaomi_mimo_llm_model_credential, XiaomiMiMoChatModel),
]

model_info_manage = (
    ModelInfoManage.builder()
    .append_model_info_list(xiaomi_mimo_llm_list)
    .append_default_model_info(xiaomi_mimo_llm_list[0])
    .build()
)


class XiaomiMiMoModelProvider(IModelProvider):
    def get_model_info_manage(self):
        return model_info_manage

    def get_model_provide_info(self):
        return ModelProvideInfo(
            provider="model_xiaomi_mimo_provider",
            name="小米 MiMo",
            icon=get_file_content(
                os.path.join(
                    PROJECT_DIR,
                    "apps",
                    "models_provider",
                    "impl",
                    "xiaomi_mimo_model_provider",
                    "icon",
                    "xiaomi_mimo_icon_svg",
                )
            ),
        )
