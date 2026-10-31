import type { RouteObject } from 'react-router-dom';
import { StaffLayout } from './layouts/StaffLayout';
import { Guard } from './pages/field/ui';
import { Dispatches, DispatchDetail } from './pages/warehouse/Dispatches';
import { Receiving } from './pages/warehouse/Receiving';
import { TodayPage, SurveyPage, JobPage } from './pages/technician/FieldPages';
import { TicketPage } from './pages/field/TicketPage';
import { SchedulePage } from './pages/manager/ManagerPages';
export const fieldRoutes: RouteObject[] = [{ element: <StaffLayout />, children: [
    { element: <Guard roles={['warehouse', 'director']}/>, children: [
            { path: '/warehouse/dispatches', element: <Dispatches /> },
            { path: '/warehouse/dispatches/:id', element: <DispatchDetail /> },
            { path: '/warehouse/receiving', element: <Receiving /> },
        ] },
    { element: <Guard roles={['technician']}/>, children: [
            { path: '/technician/today', element: <TodayPage /> },
            { path: '/technician/surveys/:id', element: <SurveyPage /> },
            { path: '/technician/jobs/:id', element: <JobPage /> },
            { path: '/technician/tickets/:id', element: <TicketPage technician/> },
        ] },
    { element: <Guard roles={['manager']}/>, children: [
            { path: '/manager/schedule', element: <SchedulePage /> },
        ] },
    { element: <Guard roles={['support']}/>, children: [
            { path: '/support/tickets/:id', element: <TicketPage /> },
        ] },
] }];
