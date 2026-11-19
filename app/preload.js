const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('sld', {
  library: () => ipcRenderer.invoke('library'),
  generate: (form) => ipcRenderer.invoke('generate', form),
  history: () => ipcRenderer.invoke('history'),
  loadProject: (file) => ipcRenderer.invoke('load-project', file),
  openPath: (p) => ipcRenderer.invoke('open-path', p),
  showInFolder: (p) => ipcRenderer.invoke('show-in-folder', p),
  readText: (p) => ipcRenderer.invoke('read-text', p),
  parse: (text) => ipcRenderer.invoke('llm:parse', text),
  getSettings: () => ipcRenderer.invoke('settings:get'),
  saveSettings: (s) => ipcRenderer.invoke('settings:save', s),
  version: () => ipcRenderer.invoke('app:version'),
  checkUpdate: () => ipcRenderer.invoke('update:check'),
  applyUpdate: () => ipcRenderer.invoke('update:apply'),
  restart: () => ipcRenderer.invoke('update:restart'),
  openExternal: (url) => ipcRenderer.invoke('open-external', url),
  searchInvoices: (a) => ipcRenderer.invoke('inv:search', a),
  invoiceDetail: (id) => ipcRenderer.invoke('inv:detail', id),
  onUpdate: (fn) => ipcRenderer.on('update:status', (_e, p) => fn(p)),
});
