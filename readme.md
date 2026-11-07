# 面向命令行程序的结构化模糊测试与崩溃复现平台

以开源 JSON 工具 jq 为例。平台读取待测目录中的 `target.json` 和正常种子，在独立进程中执行变异输入，捕获崩溃、按签名去重并缩减反例。Python 标准库即可运行平台。项目使用 Codex 协助选题、开发和调试。

[实验报告](results/report.md) · [演示录像](video/demo.mp4) · [作业提交指南](submission.md) · [开发对话](prompt/conversation.md)

## 快速运行

需要 Python 3.10 或更新版本。提供 Windows x64、Linux x64、macOS x64 和 macOS arm64 的官方 jq 二进制安装逻辑。交付的实测结果来自 Windows x64 和 Python 3.12。下列命令从仓库根目录执行。

```sh
python code/setup_jq.py
python code/fuzz.py run targets/jq-1.8.0 --strategy structured --seed 7 --budget 100 --out runs/demo
python code/fuzz.py replay targets/jq-1.8.0 runs/demo/bug-001/minimized.jq
python code/fuzz.py replay targets/jq-1.8.1 runs/demo/bug-001/minimized.jq
```

安装脚本核对固定 SHA-256。若自动下载超时，可从 [1.8.0 发布页](https://github.com/jqlang/jq/releases/tag/jq-1.8.0) 和 [1.8.1 发布页](https://github.com/jqlang/jq/releases/tag/jq-1.8.1) 手动下载对应架构文件，再执行 `python code/setup_jq.py --old-file <旧版文件路径> --fixed-file <新版文件路径>`。每次测试指定一个新的输出目录，防止覆盖已有报告。

实验从五份正常脚本开始。记录中的第 6 次执行触发断言，52 字节输入缩减为 2 字节。旧版重放仍触发同一断言，修复版报告普通语法错误。缺陷由上游公开记录，实验展示平台的自动重新发现。 [上游缺陷 #3348](https://github.com/jqlang/jq/issues/3348) · [修复 PR #3350](https://github.com/jqlang/jq/pull/3350)

## 运行对照实验

```sh
python code/experiment.py targets/jq-1.8.0 --budget 100 --seeds 7 17 37 --out runs/experiment
python code/fuzz.py run targets/jq-json-sort --strategy structured --seed 19 --budget 75 --out runs/json-boundaries
python code/check_sort.py targets/jq-json-sort --out runs/sort-properties.json
python -m unittest discover -s code -p 'test_*.py' -v
```

两种变异使用同一构建、种子和执行预算。字节模式插入、删除或翻转字节。结构化模式基于 jq 词元修改输入，也会生成小型表达式；JSON 模式操作解析后的树。判定器区分程序正常结束、约定的拒绝码、可确认崩溃、超时、启动失败与其他退出。报告保存退出码、标准输出和错误输出、故障签名、输入及重放方法。

## 接入其他命令行程序

把目标程序、配置和种子放在同一目录。运行 `python code/fuzz.py run <目标目录> --out runs/other`。清单中的 `command` 是参数数组，`{target}` 展开为目标目录，`{input}` 展开为当次样本文件。设置 `"stdin": true` 可通过标准输入喂入样本。通用输入模式使用 `"mode": "bytes"`。每例从独立的临时工作目录执行。

## 可选的编译器覆盖反馈

平台支持 `guided`，可根据实际新增的代码覆盖保留样本。交付中的 Windows 预编译二进制没有插桩，实测对照采用 `bytes` 和 `structured` 两组。代码同时提供 Linux Clang 插桩构建入口，此构建未在交付机器上验证。

在具备 Clang、make、Bash 的 Linux 环境，从 [jq 1.8.0 发布页](https://github.com/jqlang/jq/releases/tag/jq-1.8.0) 下载并解压正式发布的 `jq-1.8.0.tar.gz`。运行以下命令后，三组共用同一插桩目标。

```sh
bash code/coverage/build.sh /path/to/jq-1.8.0
python3 code/experiment.py targets/jq-coverage --guided --out runs/coverage
```

## 仓库结构

| 路径 | 内容 |
|---|---|
| `readme.md` | 安装、测试与重放方法 |
| `code/` | 平台、变异器、实验脚本和测试 |
| `targets/` | 待测目录清单与正常种子 |
| `video/` | 实际运行生成的 MP4 和终端时间线 |
| `prompt/` | 项目对话与开发记录 |
| `results/` | 机器可读结果、反例、对照实验和实验报告 |
| `submission.md` | 课程要求核对及提交步骤 |

平台代码采用 [MIT 许可证](LICENSE)。jq 及其依赖遵循[上游许可证](https://github.com/jqlang/jq/blob/jq-1.8.0/COPYING)，二进制由安装脚本从上游取得。
