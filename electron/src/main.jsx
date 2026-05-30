// ==================== 依赖导入 ====================
// React 核心库
import React from 'react';
// React 18 的 createRoot API，用于创建根渲染节点
import ReactDOM from 'react-dom/client';
// 应用根组件
import App from './App';
// 全局样式
import './index.css';

// ==================== 应用挂载 ====================
// 获取 index.html 中的 #root DOM 节点，创建 React 根节点
// StrictMode 会在开发模式下启用额外的检查和警告（不影响生产构建）
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
