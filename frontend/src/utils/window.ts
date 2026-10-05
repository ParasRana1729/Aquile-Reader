let isTauriEnv = false;

try {
  // @ts-ignore
  isTauriEnv = typeof window !== 'undefined' && ('__TAURI_INTERNALS__' in window || '__TAURI__' in window);
} catch {
  isTauriEnv = false;
}

export async function minimizeWindow(): Promise<void> {
  try {
    const { getCurrentWindow } = await import('@tauri-apps/api/window');
    await getCurrentWindow().minimize();
  } catch (e1) {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      await invoke('minimize_window');
    } catch (e2) {
      console.log('Window minimize simulated (web mode)');
    }
  }
}

export async function toggleMaximizeWindow(): Promise<boolean> {
  try {
    const { getCurrentWindow } = await import('@tauri-apps/api/window');
    const win = getCurrentWindow();
    await win.toggleMaximize();
    return await win.isMaximized();
  } catch (e1) {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      const isMax = await invoke<boolean>('toggle_maximize_window');
      return isMax;
    } catch (e2) {
      console.log('Window maximize simulated (web mode)');
      return false;
    }
  }
}

export async function closeWindow(): Promise<void> {
  try {
    const { getCurrentWindow } = await import('@tauri-apps/api/window');
    await getCurrentWindow().close();
  } catch (e1) {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      await invoke('close_window');
    } catch (e2) {
      console.log('Window close simulated (web mode)');
    }
  }
}

export async function isWindowMaximized(): Promise<boolean> {
  try {
    const { getCurrentWindow } = await import('@tauri-apps/api/window');
    return await getCurrentWindow().isMaximized();
  } catch (e1) {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      return await invoke<boolean>('is_window_maximized');
    } catch (e2) {
      return false;
    }
  }
}
