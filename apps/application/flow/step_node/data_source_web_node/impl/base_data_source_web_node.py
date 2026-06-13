# coding=utf-8
"""
    @project: MaxKB
    @Author：niu
    @file： base_data_source_web_node.py
    @date：2025/11/12 13:47
    @desc:
"""

from django.utils.translation import gettext_lazy as _

from application.flow.i_step_node import NodeResult
from application.flow.step_node.data_source_web_node.i_data_source_web_node import IDataSourceWebNode
from common import forms
from common.forms import BaseForm


class BaseDataSourceWebNodeForm(BaseForm):
    source_url = forms.TextInputField(_('Web source url'), required=True, attrs={
        'placeholder': _('Please enter the Web root address')})
    selector = forms.TextInputField(_('Web knowledge selector'), required=False, attrs={
        'placeholder': _('The default is body, you can enter .classname/#idname/tagname')})


class BaseDataSourceWebNode(IDataSourceWebNode):
    def save_context(self, details, workflow_manage):
        self.context['exception_message'] = details.get('err_message')

    @staticmethod
    def get_form_list(node):
        return BaseDataSourceWebNodeForm().to_form_list()

    def execute(self, **kwargs) -> NodeResult:
        BaseDataSourceWebNodeForm().valid_form(self.workflow_params.get("data_source"))

        data_source = self.workflow_params.get("data_source")

        source_url = data_source.get("source_url")
        selector = data_source.get("selector") or "body"

        return NodeResult(
            {
                'document_list': [],
                'source_url': source_url,
                'selector': selector,
                'err_message': _('Web crawling is disabled in knowledge-only mode.'),
            },
            self.workflow_manage.params.get('knowledge_base') or {},
        )

    def get_details(self, index: int, **kwargs):
        return {
            'name': self.node.properties.get('stepName'),
            "index": index,
            'run_time': self.context.get('run_time'),
            'type': self.node.type,
            'input_params': {"source_url": self.context.get("source_url"), "selector": self.context.get('selector')},
            'output_params': self.context.get('document_list'),
            'knowledge_base': self.workflow_params.get('knowledge_base'),
            'status': self.status,
            'err_message': self.err_message,
            'enableException': self.node.properties.get('enableException'),
        }
