import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { Page_SurveyRead_, Page_TicketRead_ } from '../field/contracts';
import { Card, State, Pager, useLoad, date } from '../field/ui';
export function Assignments() {
    const [sp, setSp] = useState(1), [tp, setTp] = useState(1);
    const surveys = useLoad<Page_SurveyRead_>(`/surveys?mine=true&page=${sp}`), tickets = useLoad<Page_TicketRead_>(`/tickets?assigned_to_me=true&page=${tp}`);
    return <><Card><h2>All my surveys</h2><State q={surveys} empty={!surveys.data?.items.length}/>{surveys.data?.items.map(s => <p key={s.id}><Link to={`/technician/surveys/${s.id}`}>{s.contact_name ?? `Survey #${s.id}`} · {s.status}</Link><br />{date(s.scheduled_at)} · {s.contact_phone} · {s.address_line}</p>)}{surveys.data && <Pager page={sp} set={setSp} total={surveys.data.total} size={20}/>}</Card><Card><h2>All my repair visits</h2><State q={tickets} empty={!tickets.data?.items.length}/>{tickets.data?.items.map(t => <p key={t.id}><Link to={`/technician/tickets/${t.id}`}>{t.ticket_number} · {t.status}</Link><br />{date(t.visit_date)} · {t.issue_description}</p>)}{tickets.data && <Pager page={tp} set={setTp} total={tickets.data.total} size={20}/>}</Card></>;
}
