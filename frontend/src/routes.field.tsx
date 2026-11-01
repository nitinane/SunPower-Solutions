import { SurveyorAssignments } from './pages/technician/Assignments';
import { routeRoles } from './navigation';
import type { RouteObject } from 'react-router-dom';
import { StaffLayout } from './layouts/StaffLayout';
import { Guard } from './pages/field/ui';
import { Dispatches, DispatchDetail } from './pages/warehouse/Dispatches';
import { Receiving } from './pages/warehouse/Receiving';
import { TodayPage, SurveyPage, JobPage } from './pages/technician/FieldPages';
import { TicketPage } from './pages/field/TicketPage';
import { SchedulePage } from './pages/manager/ManagerPages';
const screens: [string, React.ReactNode][] = [
    ['/warehouse/dispatches', <Dispatches />],
    ['/warehouse/dispatches/:id', <DispatchDetail />],
    ['/warehouse/receiving', <Receiving />],
    ['/technician/today', <TodayPage />],
    ['/technician/surveys/:id', <SurveyPage />],
    ['/technician/jobs/:id', <JobPage />],
    ['/technician/tickets/:id', <TicketPage technician/>],
    ['/surveyor/surveys', <SurveyorAssignments />],
    ['/surveyor/surveys/:id', <SurveyPage />],
    ['/manager/schedule', <SchedulePage />],
    ['/support/tickets/:id', <TicketPage />],
]
export const fieldRoutes: RouteObject[] = [{
    element: <StaffLayout />,
    children: screens.map(([path, element]) => ({
        element: <Guard roles={routeRoles[path]}/>,
        children: [{ path, element }],
    })),
}]
