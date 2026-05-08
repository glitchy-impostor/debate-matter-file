import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter } from "react-router-dom";
import App from "./App.jsx";
import { ToastProvider } from "./components/Toast.jsx";
import { MatterProvider } from "./lib/matterContext.jsx";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <HashRouter>
      <ToastProvider>
        <MatterProvider>
          <App />
        </MatterProvider>
      </ToastProvider>
    </HashRouter>
  </React.StrictMode>,
);
