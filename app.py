from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, send_file
import os
import csv
import datetime
import mimetypes
import shutil
from functools import wraps
from werkzeug.utils import secure_filename
import pandas as pd
from pyecharts.charts import Pie, Bar, Line, Scatter, Calendar, HeatMap, Radar, Sankey, WordCloud
from pyecharts import options as opts
from pyecharts.globals import ThemeType
from markupsafe import Markup
from pyecharts.commons.utils import JsCode
import jieba
from collections import Counter
import numpy as np

app = Flask(__name__)
app.secret_key = os.urandom(24)  # 用于session加密

# 文件上传配置
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'md'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 限制上传文件大小为32MB

# 确保上传目录存在
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# 辅助函数
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_users():
    users = []
    with open('users.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            users.append(row)
    return users

def authenticate_user(username, password):
    users = get_users()
    for user in users:
        if user['username'] == username and user['password'] == password:
            return user
    return None

def log_action(username, action, details):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open('logs.csv', 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, username, action, details])

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session or session['user']['role'] != 'admin':
            flash('需要管理员权限才能访问此页面')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def get_file_type_icon(file_type):
    """获取文件类型对应的图标"""
    if file_type.lower() in ['doc', 'docx']:
        return 'fa-file-word-o'
    elif file_type.lower() == 'pdf':
        return 'fa-file-pdf-o'
    elif file_type.lower() in ['xls', 'xlsx']:
        return 'fa-file-excel-o'
    elif file_type.lower() in ['ppt', 'pptx']:
        return 'fa-file-powerpoint-o'
    elif file_type.lower() in ['jpg', 'jpeg', 'png', 'gif']:
        return 'fa-file-image-o'
    elif file_type.lower() in ['zip', 'rar', '7z']:
        return 'fa-file-archive-o'
    elif file_type.lower() in ['txt', 'md']:
        return 'fa-file-text-o'
    else:
        return 'fa-file-o'

def parse_chinese_date(date_str):
    """解析中文日期格式"""
    try:
        # 如果已经是标准格式，直接返回
        return pd.to_datetime(date_str)
    except:
        try:
            # 处理"2月15日"格式
            import re
            pattern = r'(\d+)月(\d+)日'
            match = re.match(pattern, date_str)
            if match:
                month, day = match.groups()
                # 假设是当前年份
                year = datetime.datetime.now().year
                return pd.to_datetime(f'{year}-{month}-{day}')
            return pd.NaT
        except:
            return pd.NaT

# 路由
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = authenticate_user(username, password)
        
        if user:
            session['user'] = user
            log_action(username, '用户登录', f'用户 {username} 登录成功')
            flash(f'欢迎, {user["fullname"]}!')
            return redirect(request.args.get('next') or url_for('index'))
        else:
            flash('用户名或密码错误')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    if 'user' in session:
        log_action(session['user']['username'], '用户登出', f'用户 {session["user"]["username"]} 登出系统')
        session.pop('user', None)
    flash('您已成功登出系统')
    return redirect(url_for('index'))

@app.route('/visualization')
@login_required
def visualization():
    return render_template('visualization.html')

@app.route('/file_sharing')
@login_required
def file_sharing():
    current_path = request.args.get('path', '')
    
    # 验证路径安全性，防止路径遍历攻击
    if '..' in current_path:
        flash('无效的路径')
        return redirect(url_for('file_sharing'))
    
    # 构建当前目录的完整路径
    current_dir = os.path.join(app.config['UPLOAD_FOLDER'], current_path)
    
    # 如果目录不存在，回到根目录
    if not os.path.exists(current_dir) or not os.path.isdir(current_dir):
        flash('目录不存在')
        return redirect(url_for('file_sharing'))
    
    files = []
    for filename in os.listdir(current_dir):
        file_path = os.path.join(current_dir, filename)
        if os.path.isfile(file_path):
            file_type = os.path.splitext(filename)[1][1:].upper() if '.' in filename else ''
            file_info = {
                'name': filename,
                'size': os.path.getsize(file_path),
                'modified': datetime.datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S'),
                'type': file_type,
                'is_folder': False,
                'path': os.path.join(current_path, filename) if current_path else filename
            }
            files.append(file_info)
        elif os.path.isdir(file_path):
            # 添加文件夹
            folder_info = {
                'name': filename,
                'size': 0,  # 文件夹大小计算比较耗时，这里简化处理
                'modified': datetime.datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S'),
                'type': 'folder',
                'is_folder': True,
                'path': os.path.join(current_path, filename) if current_path else filename
            }
            files.append(folder_info)
    
    # 按照修改时间排序，最新的排在前面
    files.sort(key=lambda x: x['modified'], reverse=True)
    
    # 构建面包屑导航
    breadcrumbs = []
    if current_path:
        parts = current_path.split(os.sep)
        path_so_far = ""
        breadcrumbs.append({'name': '主目录', 'path': ''})
        for i, part in enumerate(parts):
            if part:
                path_so_far = os.path.join(path_so_far, part)
                breadcrumbs.append({'name': part, 'path': path_so_far})
    else:
        breadcrumbs.append({'name': '主目录', 'path': ''})
    
    return render_template('file_sharing.html', files=files, current_path=current_path, breadcrumbs=breadcrumbs)

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        flash('没有文件')
        return redirect(url_for('file_sharing'))
    
    file = request.files['file']
    current_path = request.form.get('current_path', '')
    
    # 验证路径安全性
    if '..' in current_path:
        flash('无效的路径')
        return redirect(url_for('file_sharing'))
    
    if file.filename == '':
        flash('没有选择文件')
        return redirect(url_for('file_sharing', path=current_path))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        target_dir = os.path.join(app.config['UPLOAD_FOLDER'], current_path)
        
        # 确保目标目录存在
        if not os.path.exists(target_dir):
            flash('目标目录不存在')
            return redirect(url_for('file_sharing'))
        
        file_path = os.path.join(target_dir, filename)
        
        # 检查是否是更新现有文件
        is_update = os.path.exists(file_path)
        
        file.save(file_path)
        
        if is_update:
            log_action(session['user']['username'], '文件更新', f'用户在 {current_path} 更新了文件 {filename}')
            flash('文件更新成功')
        else:
            log_action(session['user']['username'], '文件上传', f'用户上传了文件 {filename} 到 {current_path}')
            flash('文件上传成功')
        
        return redirect(url_for('file_sharing', path=current_path))
    else:
        flash('不允许的文件类型')
        return redirect(url_for('file_sharing', path=current_path))

@app.route('/download/<path:filepath>')
@login_required
def download_file(filepath):
    # 验证路径安全性
    if '..' in filepath:
        flash('无效的路径')
        return redirect(url_for('file_sharing'))
    
    # 分离目录和文件名
    path_parts = filepath.split(os.sep)
    filename = path_parts[-1]
    directory = os.sep.join(path_parts[:-1]) if len(path_parts) > 1 else ''
    
    # 构建完整的文件路径
    full_path = os.path.join(app.config['UPLOAD_FOLDER'], directory)
    
    log_action(session['user']['username'], '文件下载', f'用户下载了文件 {filepath}')
    return send_from_directory(full_path, filename, as_attachment=True)

@app.route('/preview/<path:filepath>')
@login_required
def preview_file(filepath):
    # 验证路径安全性
    if '..' in filepath:
        flash('无效的路径')
        return redirect(url_for('file_sharing'))
    
    # 分离目录和文件名
    path_parts = filepath.split(os.sep)
    filename = path_parts[-1]
    directory = os.sep.join(path_parts[:-1]) if len(path_parts) > 1 else ''
    
    # 构建完整的文件路径
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filepath)
    
    if not os.path.exists(file_path):
        flash('文件不存在')
        return redirect(url_for('file_sharing', path=directory))
    
    file_type = os.path.splitext(filename)[1][1:].lower() if '.' in filename else ''
    
    # 记录预览操作
    log_action(session['user']['username'], '文件预览', f'用户预览了文件 {filepath}')
    
    # 图片类型直接显示
    if file_type in ['jpg', 'jpeg', 'png', 'gif']:
        return render_template('preview.html', filename=filename, file_path=filepath, file_type='image', current_path=directory)
    
    # PDF直接嵌入预览
    elif file_type == 'pdf':
        return render_template('preview.html', filename=filename, file_path=filepath, file_type='pdf', current_path=directory)
    
    # Word文档使用Office Online预览
    elif file_type in ['doc', 'docx']:
        # 假设这里使用Office Online服务嵌入预览，实际需要配置
        return render_template('preview.html', filename=filename, file_path=filepath, file_type='word', current_path=directory)
    
    # Excel文件使用Office Online预览
    elif file_type in ['xls', 'xlsx']:
        return render_template('preview.html', filename=filename, file_path=filepath, file_type='excel', current_path=directory)
    
    # 文本文件直接显示内容
    elif file_type in ['txt', 'csv', 'md']:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return render_template('preview.html', filename=filename, content=content, file_path=filepath, file_type='text', current_path=directory)
        except UnicodeDecodeError:
            flash('无法预览此文件，可能不是文本文件')
            return redirect(url_for('file_sharing', path=directory))
    
    # 其他文件类型提示下载
    else:
        flash('此文件类型不支持在线预览，请下载后查看')
        return redirect(url_for('file_sharing', path=directory))

@app.route('/create_folder', methods=['POST'])
@login_required
def create_folder():
    folder_name = request.form.get('folder_name')
    current_path = request.form.get('current_path', '')
    
    # 验证路径安全性
    if '..' in current_path:
        flash('无效的路径')
        return redirect(url_for('file_sharing'))
    
    if not folder_name:
        flash('请输入文件夹名称')
        return redirect(url_for('file_sharing', path=current_path))
    
    # 安全处理文件夹名
    folder_name = secure_filename(folder_name)
    parent_dir = os.path.join(app.config['UPLOAD_FOLDER'], current_path)
    folder_path = os.path.join(parent_dir, folder_name)
    
    if os.path.exists(folder_path):
        flash('此文件夹已存在')
        return redirect(url_for('file_sharing', path=current_path))
    
    try:
        os.makedirs(folder_path)
        log_action(session['user']['username'], '创建文件夹', f'用户在 {current_path} 创建了文件夹 {folder_name}')
        flash('文件夹创建成功')
    except Exception as e:
        flash(f'创建文件夹失败: {str(e)}')
    
    return redirect(url_for('file_sharing', path=current_path))

@app.route('/delete_file', methods=['POST'])
@login_required
def delete_file_route():
    filepath = request.form.get('filename')
    current_path = request.form.get('current_path', '')
    
    # 验证路径安全性
    if '..' in filepath or '..' in current_path:
        flash('无效的路径')
        return redirect(url_for('file_sharing'))
    
    if not filepath:
        flash('未指定文件')
        return redirect(url_for('file_sharing', path=current_path))
    
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filepath)
    
    if not os.path.exists(file_path):
        flash('文件不存在')
        return redirect(url_for('file_sharing', path=current_path))
    
    try:
        if os.path.isfile(file_path):
            os.remove(file_path)
            log_action(session['user']['username'], '删除文件', f'用户删除了文件 {filepath}')
            flash('文件删除成功')
        elif os.path.isdir(file_path):
            shutil.rmtree(file_path)
            log_action(session['user']['username'], '删除文件夹', f'用户删除了文件夹 {filepath}')
            flash('文件夹删除成功')
    except Exception as e:
        flash(f'删除失败: {str(e)}')
    
    return redirect(url_for('file_sharing', path=current_path))

@app.route('/fault_analysis')
@login_required
def fault_analysis():
    return render_template('fault_analysis.html')

@app.route('/dom_threshold_analysis')
@login_required
def dom_threshold_analysis():
    # 获取当前时间
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 读取DOM门槛数据
    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'MYSQL', 'DOM门槛梁停机异常记录表.csv')
    
    try:
        # 尝试读取不同编码
        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
        except UnicodeDecodeError:
            try:
                df = pd.read_csv(csv_path, encoding='gbk')
            except:
                try:
                    df = pd.read_csv(csv_path, encoding='latin1')
                except:
                    df = pd.read_csv(csv_path, encoding='cp1252')
        
        # 检查列数并适当处理
        actual_columns_count = len(df.columns)
        expected_columns = ['日期', '工作时间', '产线', '故障简述', '故障类型', '频次', '修复时间', '解决方式', '停机人']
        
        if actual_columns_count == len(expected_columns):
            df.columns = expected_columns
        else:
            print(f"警告：CSV文件列数({actual_columns_count})与预期不符")
            required_columns = ['故障类型', '频次', '修复时间', '故障简述', '日期', '工作时间', '产线']
            if actual_columns_count >= len(required_columns):
                for i, col_name in enumerate(required_columns):
                    if i < actual_columns_count:
                        df = df.rename(columns={df.columns[i]: col_name})
            else:
                raise ValueError(f"CSV文件列数不足，需要至少{len(required_columns)}列")
        
        # 转换日期列为日期类型，处理中文日期格式
        df['日期'] = df['日期'].apply(parse_chinese_date)
        # 删除无效日期的行
        df = df[df['日期'].notna()]
        
        # 计算近30天的故障率
        today = pd.Timestamp.now()
        thirty_days_ago = today - pd.Timedelta(days=30)
        recent_data = df[df['日期'] >= thirty_days_ago]
        
        # 计算每天的故障率
        daily_fault_rate = []
        dates = []
        
        for date, group in recent_data.groupby('日期'):
            try:
                # 计算当天的总故障时间（分钟）
                total_fault_time = group['修复时间'].astype(str).str.extract('(\d+)').astype(float).sum()
                # 从工作时间列获取实际工作时间（小时）
                work_hours = group['工作时间'].iloc[0] if '工作时间' in group.columns else 24
                # 转换为分钟
                total_work_time = float(work_hours) * 60
                # 计算故障率
                fault_rate = (total_fault_time / total_work_time) * 100
                daily_fault_rate.append(fault_rate)
                dates.append(date.strftime('%Y-%m-%d'))
            except Exception as e:
                print(f"处理日期 {date} 的数据时出错: {str(e)}")
                continue
        
        # 创建故障率折线图
        fault_rate_line = (
            Line(init_opts=opts.InitOpts(theme=ThemeType.LIGHT, width="800px", height="400px"))
            .add_xaxis(dates)
            .add_yaxis("故障率(%)", 
                      daily_fault_rate,
                      is_smooth=True,
                      label_opts=opts.LabelOpts(formatter="{c}%"))
            .set_global_opts(
                title_opts=opts.TitleOpts(title="DOM门槛 - 近30天故障率分析"),
                yaxis_opts=opts.AxisOpts(
                    type_="value",
                    axislabel_opts=opts.LabelOpts(formatter="{value}%"),
                    min_=0,
                    max_=100,
                ),
                xaxis_opts=opts.AxisOpts(
                    axislabel_opts=opts.LabelOpts(rotate=45)
                ),
                tooltip_opts=opts.TooltipOpts(
                    trigger="axis",
                    formatter="{b}<br>{a}: {c}%"
                ),
                datazoom_opts=[opts.DataZoomOpts()],
            )
        )
        
        # 计算故障类型统计
        fault_type_count = df['故障类型'].value_counts()
        
        # 创建饼图 - 故障类型分布
        pie = (
            Pie(init_opts=opts.InitOpts(theme=ThemeType.LIGHT, width="600px", height="400px"))
            .add(
                series_name="故障类型",
                data_pair=[list(z) for z in zip(fault_type_count.index, fault_type_count.values)],
                radius=["40%", "70%"],
                label_opts=opts.LabelOpts(formatter="{b}: {c} ({d}%)"),
            )
            .set_global_opts(
                title_opts=opts.TitleOpts(title="DOM门槛 - 故障类型分布"),
                legend_opts=opts.LegendOpts(orient="vertical", pos_right="5%", pos_top="middle"),
            )
        )
        
        # 创建柱状图 - 故障频次统计
        fault_frequency = df.groupby('故障简述')['频次'].sum().sort_values(ascending=False).head(10)
        bar = (
            Bar(init_opts=opts.InitOpts(theme=ThemeType.LIGHT, width="800px", height="400px"))
            .add_xaxis(fault_frequency.index.tolist())
            .add_yaxis("频次", fault_frequency.values.tolist())
            .set_global_opts(
                title_opts=opts.TitleOpts(title="DOM门槛 - 故障频次Top10"),
                xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(rotate=45)),
                datazoom_opts=[opts.DataZoomOpts()],
            )
        )
        
        # 创建折线图 - 按日期的故障次数趋势
        try:
            if '日期' in df.columns:
                date_counts = df['日期'].value_counts().sort_index()
                line = (
                    Line(init_opts=opts.InitOpts(theme=ThemeType.LIGHT, width="800px", height="400px"))
                    .add_xaxis([d.strftime('%Y-%m-%d') for d in date_counts.index])
                    .add_yaxis("故障次数", date_counts.values.tolist(), is_smooth=True)
                    .set_global_opts(
                        title_opts=opts.TitleOpts(title="DOM门槛 - 故障趋势分析"),
                        yaxis_opts=opts.AxisOpts(
                            type_="value",
                            axistick_opts=opts.AxisTickOpts(is_show=True),
                            splitline_opts=opts.SplitLineOpts(is_show=True),
                        ),
                        xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(rotate=45)),
                        datazoom_opts=[opts.DataZoomOpts()],
                    )
                )
            else:
                line = (
                    Line(init_opts=opts.InitOpts(theme=ThemeType.LIGHT, width="800px", height="400px"))
                    .add_xaxis(["数据缺失"])
                    .add_yaxis("故障次数", [0], is_smooth=True)
                    .set_global_opts(
                        title_opts=opts.TitleOpts(title="DOM门槛 - 故障趋势分析（数据缺失）"),
                    )
                )
        except Exception as e:
            print(f"处理日期趋势时出错: {str(e)}")
            line = (
                Line(init_opts=opts.InitOpts(theme=ThemeType.LIGHT, width="800px", height="400px"))
                .add_xaxis(["处理错误"])
                .add_yaxis("故障次数", [0], is_smooth=True)
                .set_global_opts(
                    title_opts=opts.TitleOpts(title="DOM门槛 - 故障趋势分析（处理错误）"),
                )
            )
        
        # 创建故障类型与工序关系图表
        try:
            # 按产线和故障类型分组统计频次
            process_fault = df.groupby(['产线', '故障类型'])['频次'].sum().unstack(fill_value=0)
            
            # 获取所有工序和故障类型
            processes = process_fault.index.tolist()
            fault_types = process_fault.columns.tolist()
            
            # 创建堆叠柱状图
            process_chart = (
                Bar(init_opts=opts.InitOpts(theme=ThemeType.LIGHT, width="1200px", height="500px"))
                .add_xaxis(processes)
            )
            
            # 为每种故障类型添加一个系列
            for fault_type in fault_types:
                process_chart.add_yaxis(
                    fault_type,
                    process_fault[fault_type].tolist(),
                    stack="stack1",
                    label_opts=opts.LabelOpts(is_show=False),
                )
            
            # 设置全局选项
            process_chart.set_global_opts(
                title_opts=opts.TitleOpts(title="DOM门槛 - 故障类型与工序关系"),
                xaxis_opts=opts.AxisOpts(
                    axislabel_opts=opts.LabelOpts(rotate=45),
                    name="工序"
                ),
                yaxis_opts=opts.AxisOpts(
                    name="故障频次",
                    type_="value",
                ),
                tooltip_opts=opts.TooltipOpts(
                    trigger="axis",
                    axis_pointer_type="shadow"
                ),
                legend_opts=opts.LegendOpts(
                    pos_top="5%",
                    orient="horizontal"
                ),
                datazoom_opts=[
                    opts.DataZoomOpts(type_="slider", orient="horizontal"),
                    opts.DataZoomOpts(type_="inside", orient="horizontal")
                ],
            )
            
        except Exception as e:
            print(f"处理故障类型与工序关系时出错: {str(e)}")
            process_chart = (
                Bar(init_opts=opts.InitOpts(theme=ThemeType.LIGHT, width="1200px", height="500px"))
                .add_xaxis(["数据处理错误"])
                .add_yaxis("错误", [0])
                .set_global_opts(
                    title_opts=opts.TitleOpts(title="DOM门槛 - 故障类型与工序关系（数据处理错误）"),
                )
            )
        
        # 渲染图表
        charts = {
            'pie_chart': Markup(pie.render_embed()),
            'bar_chart': Markup(bar.render_embed()),
            'line_chart': Markup(line.render_embed()),
            'process_chart': Markup(process_chart.render_embed()),
            'fault_rate_chart': Markup(fault_rate_line.render_embed()),
        }
        
        return render_template('dom_threshold_analysis.html', charts=charts, now=now)
    
    except Exception as e:
        return render_template('error.html', error=str(e))

@app.route('/dom_welding_analysis')
@login_required
def dom_welding_analysis():
    # 获取当前时间
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 读取DOM焊接数据
    excel_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'MYSQL', 'DOM焊接停机异常记录表.xlsx')
    
    try:
        df = pd.read_excel(excel_path)
        
        # 检查实际列数并适当调整列名
        actual_columns_count = len(df.columns)
        
        if actual_columns_count == 6:
            df.columns = ['日期', '产线', '故障简述', '故障类型', '频次', '修复时间']
        elif actual_columns_count == 9:
            df.columns = ['日期', '工作时间', '产线', '故障简述', '故障类型', '频次', '修复时间', '解决方式', '停机人']
        else:
            print(f"警告：Excel文件列数({actual_columns_count})与预期不符")
            required_columns = ['故障类型', '频次', '修复时间', '故障简述', '日期', '工作时间']
            if actual_columns_count >= len(required_columns):
                for i, col_name in enumerate(required_columns):
                    if i < actual_columns_count:
                        df = df.rename(columns={df.columns[i]: col_name})
            else:
                raise ValueError(f"Excel文件列数不足，需要至少{len(required_columns)}列")
        
        # 转换日期列为日期类型，处理中文日期格式
        df['日期'] = df['日期'].apply(parse_chinese_date)
        # 删除无效日期的行
        df = df[df['日期'].notna()]
        
        # 1. 创建热力图 - 故障类型在不同日期的分布
        try:
            # 按日期和故障类型分组计数
            heatmap_data = df.groupby(['日期', '故障类型']).size().reset_index(name='count')
            # 转换为热力图所需的格式
            dates = sorted(heatmap_data['日期'].unique())
            fault_types = sorted(heatmap_data['故障类型'].unique())
            
            # 创建日期索引字典
            date_index = {date: i for i, date in enumerate(dates)}
            fault_type_index = {fault: i for i, fault in enumerate(fault_types)}
            
            # 准备数据
            heat_data = []
            for _, row in heatmap_data.iterrows():
                heat_data.append([
                    date_index[row['日期']], 
                    fault_type_index[row['故障类型']], 
                    row['count']
                ])
            
            heatmap = (
                HeatMap(init_opts=opts.InitOpts(theme=ThemeType.LIGHT, width="1200px", height="400px"))
                .add_xaxis([d.strftime('%Y-%m-%d') for d in dates])
                .add_yaxis(
                    "故障类型",
                    fault_types,
                    heat_data,
                    label_opts=opts.LabelOpts(is_show=True, formatter="{c}"),
                )
                .set_global_opts(
                    title_opts=opts.TitleOpts(title="DOM焊接 - 故障类型热力分布"),
                    visualmap_opts=opts.VisualMapOpts(),
                    xaxis_opts=opts.AxisOpts(
                        axislabel_opts=opts.LabelOpts(rotate=45)
                    ),
                )
            )
        except Exception as e:
            print(f"创建热力图时出错: {str(e)}")
            heatmap = create_error_chart("热力图")
        
        # 2. 创建雷达图 - 不同时间段的故障类型分布
        try:
            # 添加周几信息
            df['星期'] = df['日期'].dt.day_name()
            # 按星期和故障类型统计频次
            radar_data = df.pivot_table(
                values='频次',
                index='故障类型',
                columns='星期',
                aggfunc='sum',
                fill_value=0
            )
            
            # 准备雷达图数据
            c_schema = [
                {"name": day, "max": radar_data.max().max()} 
                for day in radar_data.columns
            ]
            
            radar = (
                Radar(init_opts=opts.InitOpts(theme=ThemeType.LIGHT, width="600px", height="400px"))
                .add_schema(
                    schema=c_schema,
                    shape="circle",
                )
            )
            
            # 为每个故障类型添加一条数据线
            for fault_type in radar_data.index:
                values = radar_data.loc[fault_type].tolist()
                radar.add(
                    series_name=fault_type,
                    data=[values],
                    linestyle_opts=opts.LineStyleOpts(width=2),
                    label_opts=opts.LabelOpts(is_show=False),
                )
            
            radar.set_global_opts(
                title_opts=opts.TitleOpts(title="DOM焊接 - 每周故障类型分布"),
                legend_opts=opts.LegendOpts(
                    orient="vertical",
                    pos_left="right",
                    pos_top="middle"
                )
            )
        except Exception as e:
            print(f"创建雷达图时出错: {str(e)}")
            radar = create_error_chart("雷达图")
        
        # 3. 创建箱线图 - 故障修复时间分布
        try:
            # 提取修复时间的数值
            df['修复时间_分钟'] = df['修复时间'].astype(str).str.extract('(\d+)').astype(float)
            
            # 按故障类型分组计算箱线图数据
            boxplot_data = []
            categories = []
            
            for fault_type in df['故障类型'].unique():
                data = df[df['故障类型'] == fault_type]['修复时间_分钟'].dropna().tolist()
                if data:
                    boxplot_data.append(data)
                    categories.append(fault_type)
            
            boxplot = (
                Bar(init_opts=opts.InitOpts(theme=ThemeType.LIGHT, width="1200px", height="400px"))
                .add_xaxis(categories)
                .add_yaxis(
                    "修复时间分布",
                    boxplot_data,
                    label_opts=opts.LabelOpts(is_show=False),
                )
                .set_global_opts(
                    title_opts=opts.TitleOpts(title="DOM焊接 - 故障修复时间分布"),
                    xaxis_opts=opts.AxisOpts(
                        axislabel_opts=opts.LabelOpts(rotate=45)
                    ),
                    yaxis_opts=opts.AxisOpts(
                        name="修复时间(分钟)",
                        type_="value",
                    ),
                )
            )
        except Exception as e:
            print(f"创建箱线图时出错: {str(e)}")
            boxplot = create_error_chart("箱线图")
        
        # 4. 创建桑基图 - 故障类型与解决方式的关系
        try:
            # 统计故障类型到解决方式的流向
            sankey_data = df.groupby(['故障类型', '解决方式']).size().reset_index(name='value')
            
            # 准备节点和链接数据
            nodes = []
            nodes.extend([{"name": t} for t in sankey_data['故障类型'].unique()])
            nodes.extend([{"name": s} for s in sankey_data['解决方式'].unique()])
            
            links = []
            for _, row in sankey_data.iterrows():
                links.append({
                    "source": row['故障类型'],
                    "target": row['解决方式'],
                    "value": row['value']
                })
            
            sankey = (
                Sankey(init_opts=opts.InitOpts(theme=ThemeType.LIGHT, width="1200px", height="600px"))
                .add(
                    "故障处理流程",
                    nodes,
                    links,
                    linestyle_opt=opts.LineStyleOpts(opacity=0.3, curve=0.5, color="source"),
                    label_opts=opts.LabelOpts(position="right"),
                )
                .set_global_opts(
                    title_opts=opts.TitleOpts(title="DOM焊接 - 故障处理流程分析")
                )
            )
        except Exception as e:
            print(f"创建桑基图时出错: {str(e)}")
            sankey = create_error_chart("桑基图")
        
        # 5. 创建词云图 - 故障简述的关键词分布
        try:
            # 将所有故障简述合并
            text = ' '.join(df['故障简述'].astype(str))
            # 使用jieba分词
            words = jieba.cut(text)
            # 统计词频
            word_freq = Counter(words)
            # 过滤掉单个字的词
            word_freq = {k: v for k, v in word_freq.items() if len(k) > 1}
            
            wordcloud = (
                WordCloud(init_opts=opts.InitOpts(theme=ThemeType.LIGHT, width="1200px", height="600px"))
                .add(
                    "",
                    list(word_freq.items()),
                    word_size_range=[20, 100],
                    textstyle_opts=opts.TextStyleOpts(font_family="Microsoft YaHei"),
                )
                .set_global_opts(
                    title_opts=opts.TitleOpts(title="DOM焊接 - 故障关键词分布"),
                )
            )
        except Exception as e:
            print(f"创建词云图时出错: {str(e)}")
            wordcloud = create_error_chart("词云图")
        
        # 渲染所有图表
        charts = {
            'heatmap': Markup(heatmap.render_embed()),
            'radar': Markup(radar.render_embed()),
            'boxplot': Markup(boxplot.render_embed()),
            'sankey': Markup(sankey.render_embed()),
            'wordcloud': Markup(wordcloud.render_embed()),
        }
        
        return render_template('dom_welding_analysis.html', charts=charts, now=now)
    
    except Exception as e:
        return render_template('error.html', error=str(e))

def create_error_chart(chart_type):
    """创建错误提示图表"""
    return Bar(init_opts=opts.InitOpts(width="600px", height="400px")) \
        .add_xaxis(["数据处理错误"]) \
        .add_yaxis("错误", [0]) \
        .set_global_opts(
            title_opts=opts.TitleOpts(title=f"DOM焊接 - {chart_type}（数据处理错误）"),
        )

@app.route('/blanc_threshold_analysis')
@login_required
def blanc_threshold_analysis():
    # 使用模板数据
    return render_template('blanc_threshold_analysis.html')

@app.route('/blanc_welding_analysis')
@login_required
def blanc_welding_analysis():
    # 使用模板数据
    return render_template('blanc_welding_analysis.html')

@app.route('/admin')
@admin_required
def admin_panel():
    users = get_users()
    
    # 读取日志
    logs = []
    try:
        with open('logs.csv', 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)  # 读取标题行
            for row in reader:
                if len(row) >= 4:  # 确保行有足够的列
                    logs.append({
                        'timestamp': row[0],
                        'username': row[1],
                        'action': row[2],
                        'details': row[3]
                    })
    except (FileNotFoundError, IOError):
        # 如果日志文件不存在，创建一个空的日志文件
        with open('logs.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'username', 'action', 'details'])
    
    # 按时间倒序排列
    logs.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return render_template('admin.html', users=users, logs=logs)

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """提供上传的文件以供预览"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/add_user', methods=['POST'])
@admin_required
def add_user():
    username = request.form.get('username')
    password = request.form.get('password')
    fullname = request.form.get('fullname')
    email = request.form.get('email')
    role = request.form.get('role')
    
    if not all([username, password, fullname, email, role]):
        flash('所有字段都必须填写')
        return redirect(url_for('admin_panel'))
    
    # 检查用户名是否已存在
    users = get_users()
    if any(user['username'] == username for user in users):
        flash(f'用户名 {username} 已存在')
        return redirect(url_for('admin_panel'))
    
    # 添加新用户
    try:
        with open('users.csv', 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([username, password, role, fullname, email])
        
        log_action(session['user']['username'], '添加用户', f'管理员添加了新用户 {username}')
        flash(f'成功添加用户: {username}')
    except Exception as e:
        flash(f'添加用户失败: {str(e)}')
    
    return redirect(url_for('admin_panel'))

@app.route('/delete_user', methods=['POST'])
@admin_required
def delete_user():
    username = request.form.get('username')
    
    if not username:
        flash('未指定用户')
        return redirect(url_for('admin_panel'))
    
    # 不能删除自己
    if username == session['user']['username']:
        flash('不能删除当前登录的用户')
        return redirect(url_for('admin_panel'))
    
    # 读取用户数据
    users = get_users()
    
    # 检查权限 - 管理员不能删除管理员
    target_user = next((user for user in users if user['username'] == username), None)
    if target_user and target_user['role'] == 'admin' and session['user']['role'] == 'admin' and session['user']['username'] != username:
        flash('您没有权限删除其他管理员账户')
        return redirect(url_for('admin_panel'))
    
    # 删除用户
    new_users = [user for user in users if user['username'] != username]
    
    if len(new_users) == len(users):
        flash(f'未找到用户 {username}')
        return redirect(url_for('admin_panel'))
    
    # 写回文件
    with open('users.csv', 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['username', 'password', 'role', 'fullname', 'email']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for user in new_users:
            writer.writerow(user)
    
    log_action(session['user']['username'], '删除用户', f'管理员删除了用户 {username}')
    flash(f'已删除用户: {username}')
    
    return redirect(url_for('admin_panel'))

@app.route('/reset_password', methods=['POST'])
@admin_required
def reset_password():
    username = request.form.get('username')
    new_password = request.form.get('new_password')
    
    if not username or not new_password:
        flash('缺少用户名或密码')
        return redirect(url_for('admin_panel'))
    
    # 读取用户数据
    users = get_users()
    
    # 更新密码
    updated = False
    for user in users:
        if user['username'] == username:
            user['password'] = new_password
            updated = True
            break
    
    if not updated:
        flash(f'未找到用户 {username}')
        return redirect(url_for('admin_panel'))
    
    # 写回文件
    with open('users.csv', 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['username', 'password', 'role', 'fullname', 'email']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for user in users:
            writer.writerow(user)
    
    log_action(session['user']['username'], '重置密码', f'管理员重置了用户 {username} 的密码')
    flash(f'已重置 {username} 的密码')
    
    return redirect(url_for('admin_panel'))

@app.route('/export_users')
@admin_required
def export_users():
    users = get_users()
    
    # 创建临时CSV文件
    import tempfile
    import os
    
    temp_file = tempfile.NamedTemporaryFile(delete=False, mode='w', newline='', encoding='utf-8', suffix='.csv')
    fieldnames = ['username', 'password', 'role', 'fullname', 'email']
    
    writer = csv.DictWriter(temp_file, fieldnames=fieldnames)
    writer.writeheader()
    for user in users:
        # 不导出密码
        user_copy = user.copy()
        user_copy['password'] = '*****'  # 隐藏密码
        writer.writerow(user_copy)
    
    temp_file.close()
    
    log_action(session['user']['username'], '导出用户', f'管理员导出了用户列表')
    
    return send_file(temp_file.name, as_attachment=True, download_name='users.csv')

@app.route('/export_logs')
@admin_required
def export_logs():
    try:
        log_action(session['user']['username'], '导出日志', f'管理员导出了系统日志')
        return send_file('logs.csv', as_attachment=True, download_name='system_logs.csv')
    except:
        flash('日志文件不存在')
        return redirect(url_for('admin_panel'))

@app.route('/change_role', methods=['POST'])
@admin_required
def change_role():
    username = request.form.get('username')
    new_role = request.form.get('role')
    
    if not username or not new_role:
        flash('参数不完整')
        return redirect(url_for('admin_panel'))
    
    # 读取用户数据
    users = []
    with open('users.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            users.append(row)
    
    # 修改用户角色
    updated = False
    for user in users:
        if user['username'] == username:
            user['role'] = new_role
            updated = True
            break
    
    if updated:
        # 写回文件
        with open('users.csv', 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['username', 'password', 'role', 'fullname', 'email']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for user in users:
                writer.writerow(user)
        
        log_action(session['user']['username'], '权限修改', f'管理员将用户 {username} 的角色更改为 {new_role}')
        flash(f'已将 {username} 的角色更改为 {new_role}')
    else:
        flash(f'未找到用户 {username}')
    
    return redirect(url_for('admin_panel'))

@app.route('/spare_parts')
@login_required
def spare_parts():
    """备品备件库页面"""
    try:
        # 使用os.path.join构建正确的文件路径
        csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'spare_parts.csv')
        
        # 读取CSV文件
        df = pd.read_csv(csv_path, encoding='utf-8')
        
        # 计算库存状态
        df['status'] = df.apply(lambda row: 
            'danger' if row['数量'] <= row['最小库存'] else 
            'warning' if row['数量'] <= row['最小库存'] * 1.5 else 
            'normal', axis=1)
        
        # 转换为字典列表
        parts = df.to_dict('records')
        
        # 获取库存告急的备件
        urgent_parts = df[df['数量'] <= df['最小库存']].to_dict('records')
        
        return render_template('spare_parts.html', 
                             parts=parts, 
                             urgent_parts=urgent_parts)
    except Exception as e:
        flash(f'读取备件数据失败：{str(e)}')
        return render_template('spare_parts.html', parts=[], urgent_parts=[])

@app.route('/test')
@login_required
def test():
    """测试页面"""
    # 生成当前时间
    now = datetime.datetime.now()
    
    # 生成时间序列数据（从早上8点开始）
    start_time = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if now < start_time:
        start_time = start_time - datetime.timedelta(days=1)
    
    # 生成时间点（每5秒一个点）
    time_points = []
    current_time = start_time
    while current_time <= now:
        time_points.append(current_time.strftime('%H:%M:%S'))
        current_time += datetime.timedelta(seconds=60)
    
    # 生成随机数据
    np.random.seed(now.second)  # 使用当前秒数作为随机种子
    dom_left_data = np.random.uniform(65, 87, len(time_points))
    dom_right_data = np.random.uniform(65, 87, len(time_points))
    
    # 创建折线图
    line = (
        Line(init_opts=opts.InitOpts(theme=ThemeType.LIGHT, width="1200px", height="600px"))
        .add_xaxis(time_points)
        .add_yaxis("DOM左门槛", dom_left_data.round(2).tolist(), is_smooth=True, label_opts=opts.LabelOpts(is_show=False))
        .add_yaxis("DOM右门槛", dom_right_data.round(2).tolist(), is_smooth=True, label_opts=opts.LabelOpts(is_show=False))
        .set_global_opts(
            title_opts=opts.TitleOpts(title="DOM门槛实时节拍数据"),
            xaxis_opts=opts.AxisOpts(
                type_="category",
                axislabel_opts=opts.LabelOpts(rotate=45),
                name="时间"
            ),
            yaxis_opts=opts.AxisOpts(
                type_="value",
                name="节拍(秒)",
                min_=60,
                max_=90,
                splitline_opts=opts.SplitLineOpts(is_show=True)
            ),
            tooltip_opts=opts.TooltipOpts(
                trigger="axis",
                formatter="{b}<br/>{a}: {c}秒"
            ),
            legend_opts=opts.LegendOpts(
                pos_top="5%",
                orient="horizontal"
            ),
            datazoom_opts=[
                opts.DataZoomOpts(type_="slider", range_start=99, range_end=100),
                opts.DataZoomOpts(type_="inside", range_start=99, range_end=100)
            ]
        )
    )
    
    return render_template('test.html', chart=Markup(line.render_embed()), now=now)

@app.route('/get_dom_data')
@login_required
def get_dom_data():
    """获取DOM门槛实时数据"""
    # 生成当前时间
    now = datetime.datetime.now()
    
    # 生成时间序列数据（从早上8点开始）
    start_time = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if now < start_time:
        start_time = start_time - datetime.timedelta(days=1)
    
    # 生成时间点（每5秒一个点）
    time_points = []
    current_time = start_time
    while current_time <= now:
        time_points.append(current_time.strftime('%H:%M:%S'))
        current_time += datetime.timedelta(seconds=5)
    
    # 生成随机数据
    np.random.seed(now.second)  # 使用当前秒数作为随机种子
    dom_left_data = np.random.uniform(65, 87, len(time_points))
    dom_right_data = np.random.uniform(65, 87, len(time_points))
    
    return {
        'time_points': time_points,
        'dom_left_data': dom_left_data.round(2).tolist(),
        'dom_right_data': dom_right_data.round(2).tolist(),
        'current_time': now.strftime('%Y-%m-%d %H:%M:%S')
    }

if __name__ == '__main__':
    app.run(host='192.168.50.87', port=5000, debug=True) 