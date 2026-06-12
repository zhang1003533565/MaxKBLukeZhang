const knowledgeOnlyValue = (import.meta.env.VITE_KNOWLEDGE_ONLY ?? 'true').toLowerCase()

export const isKnowledgeOnly = !['0', 'false', 'no', 'off'].includes(knowledgeOnlyValue)
