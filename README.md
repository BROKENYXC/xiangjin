# 祥晋自动化设备数据管理系统

## 项目简介
祥晋自动化设备数据管理系统是一个基于Python Flask框架开发的工业数据管理平台，用于管理和监控自动化设备运行数据、文件共享、故障分析等功能。

## 主要功能
1. **数据可视化大屏**
   - 实时展示设备运行状态
   - 支持多维度数据展示
   - 动态数据更新
   - 交互式图表操作

2. **文件共享管理**
   - 文件上传和下载
   - 文件预览功能
   - 文件分类管理
   - 权限控制

3. **故障分析系统**
   - 故障记录和追踪
   - 故障原因分析
   - 解决方案管理
   - 统计分析报表

4. **备品备件库管理**
   - 实时库存监控
   - 库存预警提醒
   - 动态数据更新
   - 数据可视化展示

## 最新更新

### 版本 3.1.0 (2024-03-xx)
1. **备品备件库功能优化**
   - 改进数据展示方式，采用表格视图替代卡片式布局
   - 实现实时数据动态更新，无需刷新页面
   - 添加库存预警功能，自动提醒库存不足的备件
   - 优化搜索功能，支持多字段快速检索

2. **数据可视化测试页面**
   - 新增DOM门槛实时节拍数据监控
   - 实现双产线数据对比展示
   - 支持动态数据更新（5秒间隔）
   - 添加数据缩放和交互功能
   - 优化图表展示效果

3. **系统性能优化**
   - 改进数据加载机制，减少页面刷新
   - 优化图表渲染性能
   - 添加错误处理和容错机制

4. **界面优化**
   - 统一系统名称和品牌标识
   - 添加公司logo
   - 优化页面布局和响应式设计
   - 改进用户交互体验

## 技术栈
- 后端：Python Flask
- 前端：HTML5, CSS3, JavaScript
- 数据库：SQLite
- 图表库：ECharts
- 文件处理：pandas

## 安装说明
1. 克隆项目到本地
2. 安装依赖包：
   ```bash
   pip install -r requirements.txt
   ```
3. 初始化数据库：
   ```bash
   python init_db.py
   ```
4. 运行应用：
   ```bash
   python app.py
   ```

## 使用说明
1. 访问系统首页：http://localhost:5000
2. 使用默认管理员账号登录：
   - 用户名：admin
   - 密码：admin123

## 目录结构
```
shengji_app/
├── app.py              # 主应用文件
├── config.py           # 配置文件
├── init_db.py          # 数据库初始化脚本
├── requirements.txt    # 项目依赖
├── static/            # 静态文件
│   ├── css/          # 样式文件
│   ├── js/           # JavaScript文件
│   └── images/       # 图片资源
├── templates/         # HTML模板
└── data/             # 数据文件
```

## 注意事项
1. 首次运行需要初始化数据库
2. 请及时修改默认管理员密码
3. 定期备份数据库文件
4. 确保data目录具有写入权限

## 版本历史
- v3.1.0: 添加备品备件库功能，优化数据可视化
- v3.0.0: 系统重构，更新界面设计
- v2.0.0: 添加文件共享功能
- v1.0.0: 初始版本发布

## 维护说明
- 定期检查日志文件
- 监控系统性能
- 及时更新依赖包
- 定期备份数据

## 联系方式
如有问题或建议，请联系系统管理员。 