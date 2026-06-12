# coding=utf-8
from enum import Enum

from models_provider.impl.aliyun_bai_lian_model_provider.aliyun_bai_lian_model_provider import (
    AliyunBaiLianModelProvider,
)
from models_provider.impl.deepseek_model_provider.deepseek_model_provider import DeepSeekModelProvider
from models_provider.impl.xf_model_provider.xf_model_provider import XunFeiModelProvider
from models_provider.impl.xiaomi_mimo_model_provider.xiaomi_mimo_model_provider import XiaomiMiMoModelProvider


class ModelProvideConstants(Enum):
    aliyun_bai_lian_model_provider = AliyunBaiLianModelProvider()
    model_xiaomi_mimo_provider = XiaomiMiMoModelProvider()
    model_xf_provider = XunFeiModelProvider()
    model_deepseek_provider = DeepSeekModelProvider()
