import { create } from 'zustand';
import {
  CarrierState,
  CurrentCarrierResponse,
  MyCarriersResponse,
} from '../types/fleetCarriers';
import { api } from '../services/api';

interface CarrierStoreState {
  // Current docked carrier
  currentCarrierInfo: CurrentCarrierResponse | null;
  currentCarrierState: CarrierState | null;
  currentCarrierLoading: boolean;
  currentCarrierError: string | null;

  // Own and squadron carriers
  myCarriers: MyCarriersResponse | null;
  myCarriersLoading: boolean;
  myCarriersError: string | null;

  // Actions
  loadCurrentCarrier: () => Promise<void>;
  loadMyCarriers: () => Promise<void>;
  clearCarrierError: () => void;
}

export const useCarrierStore = create<CarrierStoreState>((set) => ({
  // Initial state
  currentCarrierInfo: null,
  currentCarrierState: null,
  currentCarrierLoading: false,
  currentCarrierError: null,

  myCarriers: null,
  myCarriersLoading: false,
  myCarriersError: null,

  // Actions

  async loadCurrentCarrier() {
    try {
      set({
        currentCarrierLoading: true,
        currentCarrierError: null,
      });

      const info = await api.getCurrentCarrier();

      // If not docked at a carrier, clear any previous state but keep info.
      if (!info.docked_at_carrier || !info.carrier) {
        set({
          currentCarrierInfo: info,
          currentCarrierState: null,
          currentCarrierLoading: false,
        });
        return;
      }

      const state = await api.getCurrentCarrierState();

      set({
        currentCarrierInfo: info,
        currentCarrierState: state,
        currentCarrierLoading: false,
      });
    } catch (error: any) {
      // 404 from /carriers/current/state just means "not docked at a carrier".
      const status = error?.response?.status;
      if (status === 404) {
        set({
          currentCarrierState: null,
          currentCarrierLoading: false,
          currentCarrierError: null,
        });
        return;
      }

      set({
        currentCarrierLoading: false,
        currentCarrierError:
          error?.response?.data?.detail ||
          error?.message ||
          'Failed to load current carrier information',
      });
    }
  },

  async loadMyCarriers() {
    try {
      set({
        myCarriersLoading: true,
        myCarriersError: null,
      });

      const data = await api.getMyCarriers();

      set({
        myCarriers: data,
        myCarriersLoading: false,
      });
    } catch (error: any) {
      set({
        myCarriersLoading: false,
        myCarriersError:
          error?.response?.data?.detail ||
          error?.message ||
          'Failed to load carrier list',
      });
    }
  },

  clearCarrierError() {
    set({
      currentCarrierError: null,
      myCarriersError: null,
    });
  },
}));