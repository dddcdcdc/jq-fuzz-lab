# 课程作业提交指南

## 和课程要求核对

| 课程要求 | 可查看的材料 |
|---|---|
| 大模型辅助完成并开源到 GitHub | [开发对话](prompt/conversation.md)、[开发记录](prompt/development-log.md)、[许可证](LICENSE) |
| 输入待测软件所在目录 | [jq 1.8.0 目标清单](targets/jq-1.8.0/target.json)、[运行说明](readme.md) |
| 动态执行并捕获崩溃 | [平台代码](code/fuzz.py)、[运行器](code/runner.py)、[屏幕录像](video/demo.mp4) |
| 输出在待测软件中找到的缺陷 | [缺陷报告](results/demo/bug-001/report.json)、[实验报告](results/report.md) |
| 提交包含使用说明、代码、录像与完整对话 | 根目录的 `readme.md`、`code/`、`video/`、`prompt/` |

## 材料说明

- `readme.md`：安装、运行、用例套件、对照实验、接入其他程序的步骤。
- `code/`：平台本体（`fuzz.py`、`runner.py`、`mutate.py`）、确定性用例套件（`suite.py`、`build_cases.py`）、实验脚本（`experiment.py`、`check_sort.py`）与 23 项自检（`test_fuzz.py`）。
- `video/demo.mp4`：桌面实际屏幕录像，展示自检、269 条用例库（每版 263 条）在两版上的结果、一次模糊测试发现崩溃、反例缩减与两版重放。
- `prompt/conversation.md`：从选题到最终交付的完整对话；`prompt/development-log.md`：可复核的调试记录，含失败现象与修正。
- `results/`：逐例用例记录、缺陷报告与反例、对照实验原始数据、实验报告。

## 如果要自己复现

```sh
python code/setup_jq.py
python -m unittest discover -s code -p "test_*.py" -v
python code/suite.py run targets/jq-cases --out results/suite/1.8.0
python code/suite.py run targets/jq-cases --binary targets/jq-1.8.1/jq --version "jq 1.8.1" --out results/suite/1.8.1
python code/suite.py compare results/suite/1.8.0 results/suite/1.8.1 --out results/suite/comparison.json
python code/fuzz.py run targets/jq-1.8.0 --strategy structured --seed 7 --budget 100 --out runs/demo
python code/fuzz.py replay targets/jq-1.8.0 runs/demo/bug-001/minimized.jq
python code/fuzz.py replay targets/jq-1.8.1 runs/demo/bug-001/minimized.jq
```

## 发布和提交

先用未登录的浏览器窗口确认仓库可访问，并在仓库主页核对 `readme.md`、`code/`、`video/`、`prompt/` 和 `results/`。打开 `video/demo.mp4`；若浏览器页面未提供播放器，点 Download 下载播放。提交仓库主页链接即可。

如需重新发布，登录 GitHub 并从 [New repository](https://github.com/new) 新建公开仓库，建议名称为 `jq-fuzz-lab`。使用本地仓库时，进入其根目录后将下列 URL 替换为新仓库 URL。创建空仓库时保留 README、gitignore 和许可证选项未选中。

```powershell
git remote add origin https://github.com/YOUR-ACCOUNT/jq-fuzz-lab.git
git push -u origin main
```

也可解压交付 ZIP，从其中的仓库根目录选中文件与文件夹，用 GitHub 的 **Add file → Upload files** 上传，然后提交文件。仓库根目录应直接看到 `readme.md`，目录层级按上表保留。 [GitHub 上传说明](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository)

提交说明可写：

> 《面向命令行程序的结构化模糊测试与崩溃复现平台——以 jq 为例》。平台接收待测程序目录，在独立进程中执行变异输入并捕获崩溃；以 263 条带明确预期的确定性用例逐例核对正常功能、边界与错误处理，两版结果均为 263/263 且共享用例 0 处差异；随机实验覆盖 10 个种子、两种策略共 20000 次执行，自动重新发现 jq 1.8.0 的一处已公开历史缺陷，并另外捕获一处无限递归导致的内存耗尽退出，保存、缩减并重放反例，用 1.8.1 作修复对照。仓库包含平台源代码、逐例测试记录、实际屏幕录像和大模型开发对话。
