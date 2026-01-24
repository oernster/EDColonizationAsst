import { create } from 'zustand';
import { SystemColonisationData, CurrentSystem } from '../types/colonisation';

interface ColonisationStore {
  // State
  currentSystem: string | null;
  systemData: SystemColonisationData | null;
  allSystems: string[];
  loading: boolean;
  error: string | null;
 currentSystemInfo: CurrentSystem | null;
 settingsVersion: number;

 // Actions
 setCurrentSystem: (system: string | null) => void;
 setSystemData: (data: SystemColonisationData | null) => void;
 setAllSystems: (systems: string[]) => void;
 setLoading: (loading: boolean) => void;
 setError: (error: string | null) => void;
 setCurrentSystemInfo: (info: CurrentSystem | null) => void;
 clearError: () => void;
 updateSettings: () => void;
}

export const useColonisationStore = create<ColonisationStore>((set) => ({
  // Initial state
  currentSystem: null,
  systemData: null,
  allSystems: [],
  loading: false,
  error: null,
 currentSystemInfo: null,
 settingsVersion: 0,

 // Actions
 setCurrentSystem: (system) => set({ currentSystem: system }),
 setSystemData: (data) => set({ systemData: data }),
 setAllSystems: (systems) => set({ allSystems: systems }),
 setLoading: (loading) => set({ loading }),
 setError: (error) => set({ error }),
 setCurrentSystemInfo: (info) => set({ currentSystemInfo: info }),
 clearError: () => set({ error: null }),
 updateSettings: () => set((state) => ({ settingsVersion: state.settingsVersion + 1 })),
}));