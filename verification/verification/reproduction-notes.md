本题独立验收范围：

- 有效的禁网回归取 offline-regression-r2：74 passed、3 deselected，命令使用 -m "not enable_socket" 与 --disable-socket。
- acceptance-r1 的31项新功能验收：29 passed、2 failed。该目录的 regression 是因未缓存联网样本下载而主动取消的工具运行，退出码4294967295且无JUnit，不能当模型失败或通过。
- associated-file-r2 是真实PDF 2.0嵌入附件复核：2 passed、1 failed，与上一组 annotation.AF 失败属于同一缺陷。
- product-demo-r1 用独立验证脚本构造不含annotation.AF的正常示例，清理、保存及重开的8项检查通过；这不抵消关联附件路径上的失败。
- 原轨相关测试77通过包含另外3项联网标记用例，与本次禁网74通过的范围不同。test_writer.py缺PIL和其他样本下载挂起没有计入模型能力扣分。

本目录中的PDF由本地脚本生成，可直接重建。视频控制台及上述独立脚本是验证辅助工具，不冒充模型开发的用户界面。模型冻结源码未被修改。