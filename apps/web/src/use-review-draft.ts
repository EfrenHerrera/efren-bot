import { useEffect, useState } from 'react';
import type { Proposal } from '@/review-client';

export type ReviewDraft = {
  text: string;
  redirect: boolean;
  requestKey: string;
  editing: Proposal | null;
  body: string;
  editKey: string;
};

export function useReviewDraft(id: string, drafts: Map<string, ReviewDraft>) {
  const saved = drafts.get(id);
  const [text, setText] = useState(saved?.text || '');
  const [redirect, setRedirect] = useState(saved?.redirect || false);
  const [requestKey, setRequestKey] = useState(saved?.requestKey || crypto.randomUUID());
  const [editing, setEditing] = useState<Proposal | null>(saved?.editing || null);
  const [body, setBody] = useState(saved?.body || '');
  const [editKey, setEditKey] = useState(saved?.editKey || crypto.randomUUID());
  useEffect(() => {
    drafts.set(id, { text, redirect, requestKey, editing, body, editKey });
  }, [id, drafts, text, redirect, requestKey, editing, body, editKey]);
  return { text, setText, redirect, setRedirect, requestKey, setRequestKey, editing, setEditing, body, setBody, editKey, setEditKey };
}
