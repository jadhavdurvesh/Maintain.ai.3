const { app, BrowserWindow, ipcMain, net } = require('electron')
const path = require('path')

const path = require('path')

let mainWindow = null

// The desktop installer is a client for the hosted MAINTAIN AI backend.
// The Vite build embeds VITE_API_URL into the frontend bundle.
const backendUrl = process.env.MAINTAIN_AI_API_URL || 'https://maintain-ai-3.vercel.app'\nlet connectionStatus = { state: 'checking', backendUrl, checkedAt: null }\nlet connectionTimer = null\n\nfunction checkBackend() {\n  const started = Date.now()\n  const request = net.request(`${backendUrl.replace(/\\/$/, '')}/api/auth/status`)\n  let settled = false\n  const finish = (state, error = null) => {\n    if (settled) return\n    settled = true\n    connectionStatus = { state, backendUrl, latencyMs: Date.now() - started, checkedAt: new Date().toISOString(), error }\n    if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send('desktop:connection-status', connectionStatus)\n  }\n  request.on('response', response => finish(response.statusCode >= 200 && response.statusCode < 500 ? 'connected' : 'unavailable'))\n  request.on('error', error => finish('offline', error.message))\n  request.setHeader('Accept', 'application/json')\n  request.end()\n}\n\nipcMain.handle('desktop:get-backend-url', () => backendUrl)\nipcMain.handle('desktop:get-connection-status', () => connectionStatus)

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: 'MAINTAIN AI',
    backgroundColor: '#12161c',
    webPreferences: {
      contextIsolation: true,\n      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
    },
  })

  if (!app.isPackaged) {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  } else {
    mainWindow.loadFile(path.join(process.resourcesPath, 'frontend', 'index.html'))
  }

  mainWindow.on('closed', () => { mainWindow = null })
}

app.whenReady().then(() => {
  console.log('MAINTAIN AI desktop client configured for:', backendUrl)
  createWindow()\n  checkBackend()\n  connectionTimer = setInterval(checkBackend, 10000)

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('before-quit', () => { if (connectionTimer) clearInterval(connectionTimer) })\n\napp.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
