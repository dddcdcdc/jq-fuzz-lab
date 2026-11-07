# 课程作业提交指南

## 和课程要求核对

| 课程要求 | 可查看的材料 |
|---|---|
| 大模型辅助完成并开源到 GitHub | [开发对话](prompt/conversation.md)、[开发记录](prompt/development-log.md)、[许可证](LICENSE) |
| 输入待测软件所在目录 | [jq 1.8.0 目标清单](targets/jq-1.8.0/target.json)、[运行说明](readme.md) |
| 动态执行并捕获崩溃 | [平台代码](code/fuzz.py)、[运行器](code/runner.py)、[实录](video/demo.mp4) |
| 输出在待测软件中找到的缺陷 | [缺陷报告](results/demo/bug-001/report.json)、[实验报告](results/report.md) |
| 提交包含使用说明、代码、录像与完整对话 | 根目录的 `readme.md`、`code/`、`video/`、`prompt/` |

## 发布和提交

如果已有公开仓库链接，先用未登录的浏览器窗口确认可访问。在仓库主页核对 `readme.md`、`code/`、`video/`、`prompt/` 和 `results/`。打开 `video/demo.mp4`，若浏览器页面未提供播放器，点 Download 下载播放。提交仓库主页链接即可。

如果需要手动发布，登录 GitHub 并从 [New repository](https://github.com/new) 新建公开仓库，建议名称为 `jq-fuzz-lab`。使用已准备的本地仓库时，进入其根目录后将下列 URL 替换为新仓库 URL。创建空仓库时保留 README、gitignore 和许可证选项未选中。

```powershell
git remote add origin https://github.com/YOUR-ACCOUNT/jq-fuzz-lab.git
git push -u origin main
```

也可解压交付 ZIP，从其中的仓库根目录选中文件与文件夹，用 GitHub 的 **Add file → Upload files** 上传，然后提交文件。仓库根目录应直接看到 `readme.md`，目录层级按上表保留。 [GitHub 上传说明](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository)

提交说明可写：

> 《面向命令行程序的结构化模糊测试与崩溃复现平台——以 jq 为例》。平台从正常种子自动重新发现 jq 1.8.0 的一处已公开历史缺陷，保存、缩减并重放反例，使用 jq 1.8.1 作修复对照。仓库包含平台源代码、测试结果、实际运行录像和大模型开发对话。
