import { create } from 'zustand';

interface UIState {
  workspaceId: number | null;
  chatId: number | null;
  panel: 'documents' | 'settings' | null;
  selectWorkspace: (id: number | null) => void;
  selectChat: (id: number | null) => void;
  setPanel: (panel: UIState['panel']) => void;
}

// Ephemeral UI selection only. All durable state comes from the Python API.
export const useUI = create<UIState>(set => ({
  workspaceId: null, chatId: null, panel: null,
  selectWorkspace: workspaceId => set({ workspaceId, chatId: null }),
  selectChat: chatId => set({ chatId }),
  setPanel: panel => set({ panel }),
}));
