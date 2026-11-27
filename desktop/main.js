/** PanelCraft AI Electron Main Process — Bundles Python Backend & GitHub Auto-Updater */

const { app, BrowserWindow, dialog, shell } = require("electron");
const { autoUpdater } = require("electron-updater");
const { spawn } = require("child_process");
const http = require("http");
const net = require("net");
const path = require("path");

let mainWindow = null;
let backendProc = null;

function findFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.listen(0, "127.0.0.1", () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
    srv.on("error", reject);
  });
}

function waitForBackend(port, retries = 40) {
  return new Promise((resolve, reject) => {
    const attempt = (left) => {
      http
        .get(`http://127.0.0.1:${port}/api/health`, (res) => {
          if (res.statusCode === 200) resolve();
          else if (left > 0) setTimeout(() => attempt(left - 1), 250);
          else reject(new Error("Backend health check failed"));
        })
        .on("error", () => {
          if (left > 0) setTimeout(() => attempt(left - 1), 250);
          else reject(new Error("Backend failed to start"));
        });
    };
    attempt(retries);
  });
}

function startBackend(port) {
  const isPackaged = app.isPackaged;
  if (isPackaged) {
    const binName = process.platform === "win32" ? "panelcraft-backend.exe" : "panelcraft-backend";
    const binPath = path.join(process.resourcesPath, "backend", binName);
    backendProc = spawn(binPath, ["--port", String(port)], {
      stdio: "ignore",
      windowsHide: true,
    });
  } else {
    const repoRoot = path.resolve(__dirname, "..");
    const py = process.platform === "win32" ? "python" : "python3";
    backendProc = spawn(py, ["-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", String(port)], {
      cwd: repoRoot,
      stdio: "inherit",
    });
  }
}

function setupAutoUpdater() {
  if (!app.isPackaged) return;
  autoUpdater.autoDownload = true;
  autoUpdater.on("update-downloaded", (info) => {
    dialog
      .showMessageBox(mainWindow, {
        type: "info",
        buttons: ["Restart & Update", "Later"],
        title: "PanelCraft AI Update Ready",
        message: `Version ${info.version} has been downloaded. Restart now to apply the update?`,
      })
      .then((res) => {
        if (res.response === 0) autoUpdater.quitAndInstall();
      });
  });
  autoUpdater.checkForUpdatesAndNotify().catch(() => {});
}

async function createWindow() {
  const port = await findFreePort();
  startBackend(port);
  await waitForBackend(port);

  mainWindow = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1024,
    minHeight: 680,
    title: "PanelCraft AI",
    icon: path.join(__dirname, "build", "icon.png"),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // Open GitHub Issues / Discussions / external URLs in default OS browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("https://") || url.startsWith("http://")) {
      shell.openExternal(url);
      return { action: "deny" };
    }
    return { action: "allow" };
  });

  await mainWindow.loadURL(`http://127.0.0.1:${port}/`);
  setupAutoUpdater();
}

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  if (backendProc) backendProc.kill();
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  if (backendProc) backendProc.kill();
});
