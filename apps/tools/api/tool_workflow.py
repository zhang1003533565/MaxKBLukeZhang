# coding=utf-8
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter

from common.mixins.api_mixin import APIMixin
from common.result import DefaultResultSerializer, ResultPageSerializer, ResultSerializer
from tools.serializers.tool_version import ToolVersionModelSerializer
from tools.serializers.tool_workflow import ToolWorkflowImportRequest


class ToolWorkflowApi(APIMixin):
    pass


class ToolWorkflowListVersionResult(ResultSerializer):
    def get_data(self):
        return ToolVersionModelSerializer(many=True)


class ToolWorkflowPageVersionResult(ResultPageSerializer):
    def get_data(self):
        return ToolVersionModelSerializer(many=True)


class ToolWorkflowVersionResult(ResultSerializer):
    def get_data(self):
        return ToolVersionModelSerializer()


class ToolWorkflowVersionApi(APIMixin):
    @staticmethod
    def get_parameters():
        return [
            OpenApiParameter(
                name="workspace_id",
                description="工作空间id",
                type=OpenApiTypes.STR,
                location='path',
                required=True,
            ),
            OpenApiParameter(
                name="tool_id",
                description="tool ID",
                type=OpenApiTypes.STR,
                location='path',
                required=True,
            ),
        ]


class ToolWorkflowVersionOperateApi(APIMixin):
    @staticmethod
    def get_parameters():
        return [
            OpenApiParameter(
                name="tool_version_id",
                description="工具工作流版本id",
                type=OpenApiTypes.STR,
                location='path',
                required=True,
            ),
            *ToolWorkflowVersionApi.get_parameters(),
        ]

    @staticmethod
    def get_response():
        return ToolWorkflowVersionResult


class ToolWorkflowVersionListApi(APIMixin):
    @staticmethod
    def get_parameters():
        return [
            OpenApiParameter(
                name="name",
                description="Version Name",
                type=OpenApiTypes.STR,
                required=False,
            ),
            *ToolWorkflowVersionApi.get_parameters(),
        ]

    @staticmethod
    def get_response():
        return ToolWorkflowListVersionResult


class ToolWorkflowVersionPageApi(APIMixin):
    @staticmethod
    def get_parameters():
        return ToolWorkflowVersionListApi.get_parameters()

    @staticmethod
    def get_response():
        return ToolWorkflowPageVersionResult


class ToolWorkflowExportApi(APIMixin):
    @staticmethod
    def get_parameters():
        return [
            OpenApiParameter(
                name="workspace_id",
                description="工作空间id",
                type=OpenApiTypes.STR,
                location='path',
                required=True,
            ),
            OpenApiParameter(
                name="tool_id",
                description="工具id",
                type=OpenApiTypes.STR,
                location='path',
                required=True,
            ),
        ]

    @staticmethod
    def get_response():
        return DefaultResultSerializer


class ToolWorkflowImportApi(APIMixin):
    @staticmethod
    def get_parameters():
        return ToolWorkflowExportApi.get_parameters()

    @staticmethod
    def get_request():
        return ToolWorkflowImportRequest

    @staticmethod
    def get_response():
        return DefaultResultSerializer
