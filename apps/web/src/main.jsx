import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { ThemeProvider } from "./components/ui";
import "./styles.css";

class AppErrorBoundary extends React.Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#fafafd] p-6">
        <div className="max-w-lg rounded-2xl border border-[#ffd7d2] bg-white p-6 shadow-soft">
          <p className="text-[10px] font-bold uppercase tracking-[.14em] text-[#c2564b]">Chmaba runtime error</p>
          <h1 className="mt-3 text-lg font-extrabold text-[#202128]">Page could not render</h1>
          <pre className="mt-4 max-h-64 overflow-auto whitespace-pre-wrap rounded-xl bg-[#fff5f3] p-3 text-xs leading-5 text-[#8f4b44]">{this.state.error?.stack || this.state.error?.message}</pre>
          <button onClick={() => window.location.reload()} className="mt-5 h-10 rounded-xl bg-[#6957f5] px-4 text-sm font-bold text-white">Reload page</button>
        </div>
      </div>
    );
  }
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <AppErrorBoundary>
      <ThemeProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </ThemeProvider>
    </AppErrorBoundary>
  </React.StrictMode>,
);
