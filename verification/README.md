本目录是冻结产物的独立验收原件。实际环境：Windows，Python 3.14.3，未容器化，不依赖运行期外部服务。完整依赖及真实模块路径见 environment-reviewed.json。

先安装记录中的同版 Python，检出冻结产物提交并建立虚拟环境；根据依赖记录安装测试依赖，并在检出目录用 python -m pip install -e . 安装项目（Bandit 需要这一步注册插件入口）。PyYAML 本题只验纯 Python 路径，可直接把 lib 加入 PYTHONPATH，无需编译 C 扩展。PYTHONPATH 指向检出目录、src 和 lib。各 verification 子目录保留实际 argv、原始输出、JUnit、退出码和用例。命令 JSON 中的原机绝对路径需替换为本次检出位置及相应子目录；测试断言不改。

模型原轨中的测试与本目录独立验收分开记录。原生 JSONL 和75秒连续运行录像各自只有一个，保存在对应飞书附件字段，此处不另放轨迹。工程/夹具问题按 evidence-map.json 限定归因；测试通过不等于一般性安全证明。

冻结产物提交：https://github.com/9873199/pypdf-passive-content/commit/c4dc14ffdcd69585b2cd6464611884f8452b8b81
这些独立验收文件在模型首轮结束后生成，不是模型原轨中的测试。
