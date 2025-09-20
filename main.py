from flask import Flask, request, redirect, url_for, render_template_string, Response, jsonify
import requests
import time
import threading
import uuid

app = Flask(__name__)

headers = {
    'Connection': 'keep-alive',
    'Cache-Control': 'max-age=0',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.76 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'en-US,en;q=0.9,fr;q=0.8',
    'referer': 'www.google.com'
}

logs = []
tasks = {}  # {task_id: {"thread": Thread, "paused": bool, "stop": bool, "info": {...}, "start_time": ...}}

def log_message(msg):
    logs.append(msg)
    print(msg)

# ---------------- HOME PANEL ----------------
@app.route('/')
def index():
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Henry Post Tool</title>
    <style>
        body {background: linear-gradient(to right, #9932CC, #FF00FF); font-family: Arial, sans-serif; color: white;}
        .container {background-color: rgba(0,0,0,0.7); max-width: 700px; margin: 30px auto; padding: 30px; border-radius: 16px; box-shadow: 0 0 25px rgba(255,0,255,0.4);}
        input, select {width: 100%; padding: 14px; margin: 8px 0; border-radius: 10px; border: none; font-size: 16px;}
        .button-group {display:flex; flex-direction:column; align-items:center; margin-top:15px;}
        .button-group button {width: 85%; max-width: 400px; padding: 14px; margin: 10px 0; font-size: 18px; font-weight:bold; border:none; border-radius: 10px; cursor:pointer; transition: transform 0.2s ease, box-shadow 0.3s ease;}
        .button-group button:hover {transform: scale(1.05); box-shadow: 0 0 20px #fff;}
        .start-btn {background: #FF1493; color: white;}
        .tasks-btn {background: #00CED1; color:white;}
    </style>
</head>
<body>
    <div class="container">
        <h2 style="text-align:center; margin-bottom: 20px; font-size:28px;">🚀 HENRY-X 3.0 🚀</h2>
        <form action="/" method="post" enctype="multipart/form-data">
            <label>Post / Thread ID</label>
            <input type="text" name="threadId" required>
            <label>Enter Prefix</label>
            <input type="text" name="kidx" required>
            <label>Choose Method</label>
            <select name="method" id="method" onchange="toggleFileInputs()" required>
                <option value="token">Token</option>
                <option value="cookies">Cookies</option>
            </select>

            <div id="tokenDiv">
                <label>Select Token File</label>
                <input type="file" name="tokenFile" accept=".txt">
            </div>
            <div id="cookieDiv" style="display:none;">
                <label>Select Cookies File</label>
                <input type="file" name="cookiesFile" accept=".txt">
            </div>

            <label>Comments File</label>
            <input type="file" name="commentsFile" accept=".txt" required>
            <label>Delay (Seconds)</label>
            <input type="number" name="time" min="1" required>

            <div class="button-group">
                <button type="submit" class="start-btn">▶ Start Task</button>
                <button type="button" class="tasks-btn" onclick="window.location.href='/tasks'">📋 View Tasks</button>
            </div>
        </form>
    </div>

    <script>
        function toggleFileInputs() {
            const method = document.getElementById('method').value;
            document.getElementById('tokenDiv').style.display = method === 'token' ? 'block' : 'none';
            document.getElementById('cookieDiv').style.display = method === 'cookies' ? 'block' : 'none';
        }
    </script>
</body>
</html>
''')

# ---------------- TASKS PANEL ----------------
@app.route('/tasks')
def view_tasks():
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
<title>Running Tasks</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body {background: linear-gradient(to right, #000428, #004e92); font-family: 'Segoe UI', sans-serif; color:white; text-align:center;}
h2 {margin:20px 0;}
.tasks-container {display:flex; flex-wrap:wrap; justify-content:center; gap:20px; padding:20px;}
.task-card {background: rgba(255,255,255,0.08); border-radius:16px; padding:20px; width:320px; box-shadow:0 0 20px rgba(0,255,255,0.4); transition:transform 0.2s;}
.task-card:hover {transform:scale(1.03);}
.status {margin:10px 0; font-weight:bold;}
.btn-group {display:flex; justify-content:space-around; margin-top:10px;}
.btn {padding:8px 12px; border:none; border-radius:8px; cursor:pointer; font-weight:bold; font-size:14px; transition: all 0.2s;}
.stop {background:#ff0033; color:white;}
.pause {background:#ffa500; color:white;}
.delete {background:#444; color:white;}
.btn:hover {transform:scale(1.05);}
.logs {background:#111; color:#0f0; text-align:left; margin-top:10px; padding:10px; border-radius:10px; max-height:150px; overflow:auto; font-size:13px;}
</style>
</head>
<body>
<h2>📋 Your Tasks</h2>
<div class="tasks-container" id="tasks"></div>
<script>
async function fetchTasks(){
  let res = await fetch('/tasks-data');
  let data = await res.json();
  let container = document.getElementById('tasks');
  container.innerHTML = '';
  data.forEach(t=>{
    container.innerHTML += `
    <div class="task-card">
      <h3>🧵 ${t.id}</h3>
      <div class="status">${t.stop?"🛑 Stopped":t.paused?"⏸ Paused":"✅ Running"}</div>
      <small>${t.start_time}</small>
      <div class="btn-group">
        <button class="btn stop" onclick="actionTask('stop','${t.id}')">Stop</button>
        <button class="btn pause" onclick="actionTask('pause','${t.id}')">${t.paused?"Resume":"Pause"}</button>
        <button class="btn delete" onclick="actionTask('delete','${t.id}')">Delete</button>
      </div>
      <div class="logs">${t.logs.join("<br>")}</div>
    </div>`;
  });
}
async function actionTask(act,id){
  await fetch(`/${act}-task/${id}`,{method:"POST"});
  fetchTasks();
}
fetchTasks();
setInterval(fetchTasks,3000);
</script>
</body>
</html>
''')

@app.route('/tasks-data')
def tasks_data():
    data = []
    for tid, t in tasks.items():
        data.append({
            "id": tid,
            "paused": t["paused"],
            "stop": t["stop"],
            "start_time": t["start_time"],
            "logs": t.get("logs", [])[-8:]  # last 8 logs
        })
    return jsonify(data)

@app.route('/stop-task/<task_id>', methods=['POST'])
def stop_task(task_id):
    if task_id in tasks:
        tasks[task_id]["stop"] = True
    return '', 204

@app.route('/pause-task/<task_id>', methods=['POST'])
def pause_task(task_id):
    if task_id in tasks:
        tasks[task_id]["paused"] = not tasks[task_id]["paused"]
    return '', 204

@app.route('/delete-task/<task_id>', methods=['POST'])
def delete_task(task_id):
    if task_id in tasks:
        del tasks[task_id]
    return '', 204

def comment_sender(task_id, thread_id, haters_name, speed, credentials, credentials_type, comments):
    post_url = f'https://graph.facebook.com/v15.0/{thread_id}/comments'
    i = 0
    while i < len(comments) and not tasks[task_id]["stop"]:
        if tasks[task_id]["paused"]:
            time.sleep(1)
            continue
        cred = credentials[i % len(credentials)]
        parameters = {'message': f"{haters_name} {comments[i].strip()}"}
        try:
            if credentials_type == 'access_token':
                parameters['access_token'] = cred
                response = requests.post(post_url, json=parameters, headers=headers)
            else:
                headers['Cookie'] = cred
                response = requests.post(post_url, data=parameters, headers=headers)
            current_time = time.strftime("%Y-%m-%d %I:%M:%S %p")
            msg = f"[{current_time}] Comment {i+1} {'✅ Sent' if response.ok else '❌ Failed'}"
            tasks[task_id]["logs"].append(msg)
        except Exception as e:
            tasks[task_id]["logs"].append(f"[!] Error: {e}")
        i += 1
        time.sleep(speed)
    tasks[task_id]["logs"].append(f"🛑 Task {task_id} finished/stopped.")

@app.route('/', methods=['POST'])
def send_message():
    method = request.form['method']
    thread_id = request.form['threadId']
    haters_name = request.form['kidx']
    speed = int(request.form['time'])
    comments = request.files['commentsFile'].read().decode().splitlines()
    if method == 'token':
        credentials = request.files['tokenFile'].read().decode().splitlines()
        credentials_type = 'access_token'
    else:
        credentials = request.files['cookiesFile'].read().decode().splitlines()
        credentials_type = 'Cookie'
    task_id = str(uuid.uuid4())[:8]
    tasks[task_id] = {"paused": False, "stop": False, "info": {"thread_id": thread_id}, "logs": [], "start_time": time.strftime("%Y-%m-%d %H:%M:%S")}
    t = threading.Thread(target=comment_sender, args=(task_id, thread_id, haters_name, speed, credentials, credentials_type, comments))
    tasks[task_id]["thread"] = t
    t.start()
    return redirect(url_for('view_tasks'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
