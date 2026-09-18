const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('maintainAI', {
  backendUrl: () => ipcRenderer.invoke('desktop:get-backend-url'),
  getConnectionStatus: () => ipcRenderer.invoke('desktop:get-connection-status'),
  onConnectionStatus: (callback) => {
    const handler = (_event, status) => callback(status)
    ipcRenderer.on('desktop:connection-status', handler)
    return () => ipcRenderer.removeListener('desktop:connection-status', handler)
  },
})
