import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import ErrorBoundary from './components/common/ErrorBoundary'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    {/* Bọc lỗi ở gốc: một lỗi render bất kỳ sẽ hiện thông báo + nút tải lại
        thay vì để trang trắng không hiệu dấu. */}
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
)
