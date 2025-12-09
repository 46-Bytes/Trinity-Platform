import { configureStore } from '@reduxjs/toolkit';
import engagementReducer from './slices/engagementReducer';
// Import other reducers as you create them
// import appReducer from './slices/appSlice';

export const store = configureStore({
  reducer: {
    engagement: engagementReducer,
    // Add other reducers here
    // app: appReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        // Ignore these action types
        ignoredActions: ['persist/PERSIST'],
      },
    }),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;