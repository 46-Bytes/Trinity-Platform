import { configureStore } from '@reduxjs/toolkit';
import engagementReducer from './slices/engagementReducer';
import toolReducer from './slices/toolReducer';
import taskReducer from './slices/tasksReducer';
import noteReducer from './slices/notesReducer';
import diagnosticReducer from './slices/diagnosticReducer';
import userReducer from './slices/userReducer';
import tagReducer from './slices/tagReducer';
import advisorClientReducer from './slices/advisorClientReducer';
import firmReducer from './slices/firmReducer';
import subscriptionReducer from './slices/subscriptionReducer';
import clientReducer from './slices/clientReducer';
// Import other reducers as you create them
// import appReducer from './slices/appSlice';

export const store = configureStore({
  reducer: {
    engagement: engagementReducer,
    tool: toolReducer,
    task: taskReducer,
    note: noteReducer,
    diagnostic: diagnosticReducer,
    user: userReducer,
    tag: tagReducer,
    advisorClient: advisorClientReducer,
    firm: firmReducer,
    subscription: subscriptionReducer,
    client: clientReducer,
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
