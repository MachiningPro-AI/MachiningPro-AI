/**
 * WorkspaceModelTree — left panel showing the part/feature/operation hierarchy.
 *
 * Displays only real data loaded from file or workflow.
 * No fabricated nodes or geometry representations.
 */

import type { CSSProperties } from 'react'
import { ChevronRight, ChevronDown, ChevronLeft, Eye, EyeOff } from 'lucide-react'
import { useLocale } from '../../i18n'
import type { TreeNode, WorkspaceFile, ConnectedWorkflow } from './WorkspaceTypes'
import { COLLAPSED_STRIP_W } from './WorkspaceTypes'
import { useState, useCallback } from 'react'

// ---------------------------------------------------------------------------
// Icon mapping
// ---------------------------------------------------------------------------

const NODE_ICONS: Record<string, string> = {
  root:      '◈',
  body:      '⬡',
  face:      '▭',
  edge:      '—',
  feature:   '⬟',
  hole:      '◎',
  pocket:    '⬡',
  slot:      '⬡',
  step:      '⬡',
  shoulder:  '⬡',
  setup:     '⊕',
  operation: '▶',
  toolpath:  '⟿',
  wcs:       '⊛',
  stock:     '□',
  fixture:   '⊠',
  constraint:'⊟',
}

// ---------------------------------------------------------------------------
// Build tree from workspace state
// ---------------------------------------------------------------------------

function buildTreeFromFile(wsFile: WorkspaceFile | null, vtxCount: number, triCount: number): TreeNode[] {
  if (!wsFile) return []
  return [{
    id:    'root',
    label: wsFile.name,
    type:  'root',
    visible:  true,
    expanded: true,
    badge: wsFile.format,
    children: [
      ...(vtxCount > 0 ? [{
        id:       'body-0',
        label:    `Mesh (${triCount.toLocaleString()} triangles)`,
        type:     'body' as const,
        visible:  true,
        expanded: false,
        children: [],
      }] : []),
    ],
  }]
}

function buildTreeFromWorkflow(wf: ConnectedWorkflow): TreeNode[] {
  const operationNodes: TreeNode[] = wf.operations.map(op => ({
    id:       `op-${op.operationId}`,
    label:    op.name || op.type,
    type:     'operation' as const,
    visible:  true,
    expanded: false,
    badge:    op.status,
    children: [],
    data:     { operationId: op.operationId, type: op.type, toolRef: op.toolRef },
  }))

  return [{
    id:    `wf-${wf.workflowId}`,
    label: wf.partName ?? wf.workflowId,
    type:  'root',
    visible:  true,
    expanded: true,
    badge:    wf.planStatus ?? undefined,
    children: operationNodes.length > 0 ? [{
      id:       'setup-root',
      label:    `Setups / Operations (${operationNodes.length})`,
      type:     'setup' as const,
      visible:  true,
      expanded: true,
      children: operationNodes,
    }] : [],
  }]
}

// ---------------------------------------------------------------------------
// TreeRow
// ---------------------------------------------------------------------------

interface TreeRowProps {
  node: TreeNode
  depth: number
  selectedId: string | null
  onSelect: (id: string) => void
  onToggle: (id: string) => void
  onVisibility: (id: string) => void
}

function TreeRow({ node, depth, selectedId, onSelect, onToggle, onVisibility }: TreeRowProps) {
  const icon   = NODE_ICONS[node.type] ?? '·'
  const hasKids = node.children.length > 0
  const isSelected = node.id === selectedId

  return (
    <>
      <div
        role="treeitem"
        aria-selected={isSelected}
        style={{ paddingLeft: `${8 + depth * 14}px` }}
        className={`group flex items-center gap-1 h-7 cursor-pointer select-none text-[12px]
          ${isSelected
            ? 'bg-tp-accent/15 text-tp-accent-light border-l-2 border-tp-accent'
            : 'text-tp-text-2 hover:bg-tp-surface-2 border-l-2 border-transparent'
          }`}
        onClick={() => onSelect(node.id)}
      >
        {/* Expand/collapse */}
        <span
          className="shrink-0 w-4 flex items-center justify-center text-tp-text-3"
          onClick={e => { e.stopPropagation(); hasKids && onToggle(node.id) }}
        >
          {hasKids
            ? (node.expanded ? <ChevronDown size={11} /> : <ChevronRight size={11} />)
            : <span className="w-3" />
          }
        </span>

        {/* Type icon */}
        <span className="shrink-0 text-tp-text-3 w-4 text-center leading-none">{icon}</span>

        {/* Label */}
        <span className="flex-1 truncate">{node.label}</span>

        {/* Badge */}
        {node.badge && (
          <span className="mr-1 shrink-0 text-[8px] font-mono px-1 py-px rounded
                           bg-tp-border/40 text-tp-text-3 uppercase">
            {node.badge}
          </span>
        )}

        {/* Visibility toggle */}
        <button
          type="button"
          aria-label={node.visible ? 'Hide' : 'Show'}
          onClick={e => { e.stopPropagation(); onVisibility(node.id) }}
          className="shrink-0 w-5 h-5 flex items-center justify-center
                     opacity-0 group-hover:opacity-100 transition-opacity
                     text-tp-text-3 hover:text-tp-text-2 mr-1"
        >
          {node.visible ? <Eye size={11} /> : <EyeOff size={11} />}
        </button>
      </div>

      {/* Children */}
      {node.expanded && node.children.map(child => (
        <TreeRow
          key={child.id}
          node={child}
          depth={depth + 1}
          selectedId={selectedId}
          onSelect={onSelect}
          onToggle={onToggle}
          onVisibility={onVisibility}
        />
      ))}
    </>
  )
}

// ---------------------------------------------------------------------------
// WorkspaceModelTree
// ---------------------------------------------------------------------------

export interface ModelTreeProps {
  wsFile:      WorkspaceFile | null
  workflow:    ConnectedWorkflow | null
  selectedId:  string | null
  onSelect:    (id: string | null) => void
  vtxCount:    number
  triCount:    number
  collapsed?:  boolean
  onCollapse?: () => void
  style?:      CSSProperties
}

export default function WorkspaceModelTree({
  wsFile,
  workflow,
  selectedId,
  onSelect,
  vtxCount,
  triCount,
  collapsed = false,
  onCollapse,
  style,
}: ModelTreeProps) {
  const { t } = useLocale()

  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set(['root', 'wf-root', 'setup-root']))
  const [visibleIds,  setVisibleIds]  = useState<Set<string>>(new Set())

  const toggleExpand = useCallback((id: string) => {
    setExpandedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }, [])

  const toggleVisibility = useCallback((id: string) => {
    setVisibleIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }, [])

  // Build node tree with controlled expand/visible states
  const applyState = useCallback((nodes: TreeNode[]): TreeNode[] => {
    return nodes.map(n => ({
      ...n,
      expanded: expandedIds.has(n.id),
      visible:  !visibleIds.has(n.id),
      children: applyState(n.children),
    }))
  }, [expandedIds, visibleIds])

  const rawNodes = workflow
    ? buildTreeFromWorkflow(workflow)
    : buildTreeFromFile(wsFile, vtxCount, triCount)

  const nodes = applyState(rawNodes)

  const isEmpty = !wsFile && !workflow

  // Collapsed strip — MUST 3
  if (collapsed) {
    return (
      <div
        className="h-full shrink-0 flex flex-col items-center justify-between
                   border-r border-tp-border bg-tp-surface py-1 cursor-pointer
                   hover:bg-tp-surface-2 transition-colors"
        style={{ width: `${COLLAPSED_STRIP_W}px`, minWidth: `${COLLAPSED_STRIP_W}px` }}
        role="button"
        aria-label="Expand Model Tree"
        title="Expand Model Tree"
        onClick={onCollapse}
      >
        <button
          type="button"
          className="text-tp-text-3 hover:text-tp-text p-1"
          onClick={e => { e.stopPropagation(); onCollapse?.() }}
          aria-label="Expand"
        >
          <ChevronRight size={14} />
        </button>
        <div className="flex-1 flex items-center justify-center">
          <span className="text-[9px] font-semibold uppercase tracking-widest text-tp-text-3
                           [writing-mode:vertical-rl] rotate-180">
            {t('ws_modelTree')}
          </span>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full overflow-hidden flex flex-col border-r border-tp-border bg-tp-surface"
         style={style ?? { width: '260px', minWidth: '260px' }}>
      {/* Header */}
      <div className="shrink-0 h-8 flex items-center px-3 border-b border-tp-border gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-widest text-tp-text-3 flex-1">
          {t('ws_modelTree')}
        </span>
        {onCollapse && (
          <button
            type="button"
            onClick={onCollapse}
            aria-label="Collapse Model Tree"
            title="Collapse"
            className="text-tp-text-3 hover:text-tp-text p-0.5 rounded"
          >
            <ChevronLeft size={12} />
          </button>
        )}
      </div>

      {/* Tree */}
      <div
        role="tree"
        className="flex-1 overflow-y-auto [scrollbar-width:thin]
                   [scrollbar-color:theme(colors.tp-border)_transparent]"
      >
        {isEmpty ? (
          <div className="p-3 text-[11px] text-tp-text-3 italic">
            {t('ws_noFileLoaded')}
          </div>
        ) : (
          nodes.map(node => (
            <TreeRow
              key={node.id}
              node={node}
              depth={0}
              selectedId={selectedId}
              onSelect={onSelect}
              onToggle={toggleExpand}
              onVisibility={toggleVisibility}
            />
          ))
        )}
      </div>
    </div>
  )
}
