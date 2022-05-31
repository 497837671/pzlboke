from flask import  Blueprint

main = Blueprint('main', __name__)

"""
注意，这
些模块在 app/main/__init__.py 脚本的末尾导入，这是为了避免循环导入依赖，因为在 app/
main/views.py 和 app/main/errors.py 中还要导入 main 蓝本，所以除非循环引用出现在定义
main 之后，否则会致使导入出错。
"""
# from . import <some-module> 句法表示相对导入。语句中的 . 表示当前包。
from . import views, errors
from ..models import Permission


# 把Permission类加入模板上下文
@main.app_context_processor
def inject_permissions():
    return dict(Permission=Permission)


