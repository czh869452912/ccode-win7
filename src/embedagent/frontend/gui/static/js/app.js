/**
 * EmbedAgent GUI - 前端应用
 * 使用原生 JavaScript，兼容 IE11
 */

var app = {
    ws: null,
    sessionId: null,
    currentMode: 'code',
    pendingDiff: null,
    pendingPermission: null,
    reconnectAttempts: 0,
    maxReconnectAttempts: 5,

    init: function() {
        this.connectWebSocket();
        this.bindEvents();
        this.loadWorkspace();
        this.loadFiles();
    },

    // ========== WebSocket 连接 ==========
    connectWebSocket: function() {
        var protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        var wsUrl = protocol + '//' + window.location.host + '/ws';
        
        this.ws = new WebSocket(wsUrl);
        
        var self = this;
        
        this.ws.onopen = function() {
            console.log('WebSocket connected');
            self.reconnectAttempts = 0;
            self.addSystemMessage('已连接到服务器');
        };
        
        this.ws.onmessage = function(event) {
            var data = JSON.parse(event.data);
            self.handleMessage(data);
        };
        
        this.ws.onclose = function() {
            console.log('WebSocket closed');
            self.addSystemMessage('连接已断开，尝试重连...');
            self.reconnect();
        };
        
        this.ws.onerror = function(error) {
            console.error('WebSocket error:', error);
        };
    },

    reconnect: function() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            this.addSystemMessage('重连失败，请刷新页面');
            return;
        }
        
        this.reconnectAttempts++;
        var self = this;
        setTimeout(function() {
            self.connectWebSocket();
        }, 3000);
    },

    // ========== 消息处理 ==========
    handleMessage: function(data) {
        var type = data.type;
        var payload = data.data;
        
        switch (type) {
            case 'message':
                this.addMessage(payload.type, payload.content);
                break;
            case 'stream_delta':
                this.appendStreamText(payload.text);
                break;
            case 'tool_start':
                this.addToolCard(payload, 'pending');
                break;
            case 'tool_finish':
                this.updateToolCard(payload);
                break;
            case 'tool_progress':
                this.updateToolProgress(payload);
                break;
            case 'permission_request':
                this.showPermissionModal(payload);
                break;
            case 'user_input_request':
                this.showUserInputModal(payload);
                break;
            case 'session_status':
                this.updateSessionStatus(payload);
                break;
        }
    },

    // ========== UI 操作 ==========
    bindEvents: function() {
        var self = this;
        var input = document.getElementById('messageInput');
        
        // 输入框快捷键
        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                self.sendMessage();
            }
        });
    },

    sendMessage: function() {
        var input = document.getElementById('messageInput');
        var text = input.value.trim();
        
        if (!text) return;
        
        // 如果没有会话，先创建
        if (!this.sessionId) {
            this.createSession(text);
        } else {
            this.submitMessage(text);
        }
        
        // 显示用户消息
        this.addMessage('USER', text);
        input.value = '';
        
        // 禁用发送按钮
        document.getElementById('sendBtn').disabled = true;
    },

    createSession: function(initialMessage) {
        var self = this;
        
        fetch('/api/sessions?mode=' + this.currentMode, {
            method: 'POST'
        })
        .then(function(res) { return res.json(); })
        .then(function(data) {
            self.sessionId = data.session_id;
            self.updateSessionStatus(data);
            
            if (initialMessage) {
                self.submitMessage(initialMessage);
            }
        });
    },

    submitMessage: function(text) {
        if (!this.sessionId) return;
        
        fetch('/api/sessions/' + this.sessionId + '/message', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({text: text})
        });
    },

    newSession: function() {
        this.sessionId = null;
        this.clearChat();
        this.createSession();
    },

    clearChat: function() {
        document.getElementById('chatMessages').innerHTML = '';
    },

    // ========== 消息显示 ==========
    addMessage: function(type, content) {
        var container = document.getElementById('chatMessages');
        var msgDiv = document.createElement('div');
        
        var className = 'message';
        var header = '';
        
        switch (type) {
            case 'USER':
            case 'user':
                className += ' user';
                header = '<div class="message-header">You</div>';
                break;
            case 'ASSISTANT':
            case 'assistant':
                className += ' assistant';
                header = '<div class="message-header">Assistant</div>';
                break;
            case 'SYSTEM':
            case 'system':
                className += ' system';
                break;
            case 'ERROR':
            case 'error':
                className += ' error';
                header = '<div class="message-header">Error</div>';
                break;
        }
        
        msgDiv.className = className;
        msgDiv.innerHTML = header + '<div class="message-content">' + this.escapeHtml(content) + '</div>';
        
        container.appendChild(msgDiv);
        this.scrollToBottom();
        
        // 启用发送按钮
        document.getElementById('sendBtn').disabled = false;
    },

    addSystemMessage: function(content) {
        this.addMessage('SYSTEM', content);
    },

    escapeHtml: function(text) {
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    scrollToBottom: function() {
        var container = document.getElementById('chatMessages');
        container.scrollTop = container.scrollHeight;
    },

    // ========== 流式输出 ==========
    currentStreamMessage: null,

    appendStreamText: function(text) {
        if (!this.currentStreamMessage) {
            var container = document.getElementById('chatMessages');
            var msgDiv = document.createElement('div');
            msgDiv.className = 'message assistant';
            msgDiv.innerHTML = '<div class="message-header">Assistant</div><div class="message-content"></div>';
            container.appendChild(msgDiv);
            this.currentStreamMessage = msgDiv.querySelector('.message-content');
            this.scrollToBottom();
        }
        
        this.currentStreamMessage.textContent += text;
        this.scrollToBottom();
    },

    // ========== 工具卡片 ==========
    toolCards: {},

    addToolCard: function(payload, status) {
        var container = document.getElementById('chatMessages');
        var cardDiv = document.createElement('div');
        var callId = payload.call_id;
        
        cardDiv.className = 'tool-card ' + status;
        cardDiv.id = 'tool-' + callId;
        cardDiv.innerHTML = 
            '<div class="tool-header">🔧 ' + this.escapeHtml(payload.tool_name) + '</div>' +
            '<div class="tool-args">' + this.escapeHtml(JSON.stringify(payload.arguments, null, 2)) + '</div>';
        
        container.appendChild(cardDiv);
        this.scrollToBottom();
        
        this.toolCards[callId] = cardDiv;
        this.currentStreamMessage = null;  // 结束当前流式消息
    },

    updateToolCard: function(payload) {
        var card = this.toolCards[payload.call_id];
        if (!card) return;
        
        var status = payload.success ? 'success' : 'error';
        card.className = 'tool-card ' + status;
        
        var resultHtml = '';
        if (payload.success) {
            resultHtml = '<div style="margin-top:8px;color:#2e7d32;">✓ Success</div>';
        } else {
            resultHtml = '<div style="margin-top:8px;color:#c62828;">✗ ' + this.escapeHtml(payload.error || 'Failed') + '</div>';
        }
        
        card.innerHTML += resultHtml;
    },

    updateToolProgress: function(payload) {
        // 更新工具进度
    },

    // ========== 会话状态 ==========
    updateSessionStatus: function(payload) {
        this.sessionId = payload.session_id;
        this.currentMode = payload.current_mode;
        
        document.getElementById('mode').textContent = payload.current_mode;
        
        var statusEl = document.getElementById('status');
        statusEl.textContent = payload.status;
        statusEl.className = 'status ' + payload.status;
    },

    // ========== 工作区 ==========
    loadWorkspace: function() {
        var self = this;
        
        fetch('/api/workspace')
        .then(function(res) { return res.json(); })
        .then(function(data) {
            document.getElementById('branch').textContent = data.git_branch || 'no git';
            document.getElementById('dirty').textContent = data.git_dirty + ' changes';
        });
    },

    loadFiles: function() {
        var self = this;
        
        fetch('/api/files')
        .then(function(res) { return res.json(); })
        .then(function(data) {
            self.renderFileTree(data.items);
        });
    },

    renderFileTree: function(items) {
        var container = document.getElementById('fileTree');
        var html = '';
        
        for (var i = 0; i < items.length; i++) {
            var item = items[i];
            var icon = item.kind === 'dir' ? '📁' : '📄';
            var indent = '';
            for (var j = 0; j < item.depth; j++) {
                indent += '&nbsp;&nbsp;';
            }
            html += '<div class="tree-item ' + item.kind + '" onclick="app.selectFile(\'' + item.path + '\')"\u003e' +
                indent + icon + ' ' + this.escapeHtml(item.name) + '</div>';
        }
        
        container.innerHTML = html;
    },

    selectFile: function(path) {
        // 选中文件
    },

    // ========== 权限确认 ==========
    showPermissionModal: function(payload) {
        this.pendingPermission = payload;
        document.getElementById('permTool').textContent = payload.tool_name;
        document.getElementById('permReason').textContent = payload.reason;
        document.getElementById('permissionModal').style.display = 'flex';
    },

    approvePermission: function() {
        if (!this.pendingPermission) return;
        
        this.ws.send(JSON.stringify({
            type: 'permission_response',
            permission_id: this.pendingPermission.permission_id,
            approved: true
        }));
        
        this.closePermissionModal();
    },

    rejectPermission: function() {
        if (!this.pendingPermission) return;
        
        this.ws.send(JSON.stringify({
            type: 'permission_response',
            permission_id: this.pendingPermission.permission_id,
            approved: false
        }));
        
        this.closePermissionModal();
    },

    closePermissionModal: function() {
        document.getElementById('permissionModal').style.display = 'none';
        this.pendingPermission = null;
    },

    // ========== Diff 确认 ==========
    showDiffModal: function(diff) {
        this.pendingDiff = diff;
        document.getElementById('diffPath').textContent = diff.path;
        
        // 渲染 diff
        var lines = diff.unified_diff.split('\n');
        var html = '';
        for (var i = 0; i < lines.length; i++) {
            var line = lines[i];
            var lineClass = 'diff-line';
            if (line.startsWith('+')) lineClass += ' add';
            else if (line.startsWith('-')) lineClass += ' remove';
            else if (line.startsWith('@@')) lineClass += ' header';
            
            html += '<div class="' + lineClass + '">' + this.escapeHtml(line) + '</div>';
        }
        document.getElementById('diffView').innerHTML = html;
        
        document.getElementById('diffModal').style.display = 'flex';
    },

    approveDiff: function() {
        if (!this.pendingDiff) return;
        
        // 发送确认
        this.ws.send(JSON.stringify({
            type: 'diff_approved',
            path: this.pendingDiff.path
        }));
        
        this.closeDiffModal();
    },

    rejectDiff: function() {
        this.closeDiffModal();
    },

    closeDiffModal: function() {
        document.getElementById('diffModal').style.display = 'none';
        this.pendingDiff = null;
    },

    // ========== 检查器标签 ==========
    switchTab: function(tab) {
        var tabs = document.querySelectorAll('.tab');
        for (var i = 0; i < tabs.length; i++) {
            tabs[i].classList.remove('active');
        }
        event.target.classList.add('active');
        
        if (tab === 'todos') {
            this.loadTodos();
        } else {
            document.getElementById('inspectorContent').innerHTML = '';
        }
    },

    loadTodos: function() {
        fetch('/api/todos')
        .then(function(res) { return res.json(); })
        .then(function(data) {
            var html = '<h4>Todos</h4>';
            for (var i = 0; i < data.todos.length; i++) {
                var todo = data.todos[i];
                var checked = todo.done ? '[x]' : '[ ]';
                html += '<div>' + checked + ' ' + todo.content + '</div>';
            }
            document.getElementById('inspectorContent').innerHTML = html;
        });
    },

    // ========== 用户输入请求 ==========
    showUserInputModal: function(payload) {
        // 简化实现：使用 prompt
        var options = payload.options;
        var msg = payload.question + '\n\n';
        for (var i = 0; i < options.length; i++) {
            msg += options[i].index + '. ' + options[i].text + '\n';
        }
        
        var answer = prompt(msg);
        
        this.ws.send(JSON.stringify({
            type: 'user_input_response',
            request_id: payload.request_id,
            answer: answer || ''
        }));
    }
};

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    app.init();
});
