import { useState } from 'react';
import { Card, Pill, SectionLabel, Stack } from './primitives';
import RoomShell from './RoomShell';
import ConnieTimeline from './ConnieTimeline';

function FeaturePreview({ title, description, detail }) {
  return (
    <Card padding="lg" elevated={false} style={{ borderStyle: 'dashed' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 17, color: 'var(--text-deep)' }}>
              {title}
            </div>
            <Pill tone="neutral">筹备中</Pill>
          </div>
          <div style={{ fontSize: 13, lineHeight: 1.7, color: 'var(--text-secondary)' }}>
            {description}
          </div>
          <div style={{ marginTop: 8, fontSize: 11, lineHeight: 1.6, color: 'var(--text-tertiary)' }}>
            {detail}
          </div>
        </div>
      </div>
    </Card>
  );
}

export default function PlayPage({ nav }) {
  const [showTimeline, setShowTimeline] = useState(false);

  if (showTimeline) {
    return (
      <RoomShell nav={nav}>
        <ConnieTimeline onBack={() => setShowTimeline(false)} />
      </RoomShell>
    );
  }

  return (
    <RoomShell nav={nav}>
      <div style={{ overflowY: 'auto', flex: 1, padding: '20px 16px 24px', position: 'relative', zIndex: 10 }}>
        <div style={{ marginBottom: 'var(--space-6)' }}>
          <SectionLabel>Connie 的世界</SectionLabel>
          <Card
            padding="lg"
            onClick={() => setShowTimeline(true)}
            aria-label="打开 Connie 的生活日志和碎碎念"
            style={{ animation: 'card-in 180ms ease' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              <div style={{
                width: 44, height: 44, borderRadius: 12, flexShrink: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: 'var(--accent-subtle)',
              }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.5" aria-hidden="true">
                  <path d="M12 6v6l4 2"/><circle cx="12" cy="12" r="10"/>
                </svg>
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-primary)' }}>
                  生活日志和碎碎念
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 3, lineHeight: 1.5 }}>
                  看他醒来、游荡、想起你的真实记录
                </div>
              </div>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-tertiary)" strokeWidth="1.5" aria-hidden="true">
                <path d="M9 18l6-6-6-6"/>
              </svg>
            </div>
          </Card>
        </div>

        <Stack gap="lg">
          <div>
            <SectionLabel>一起做的事</SectionLabel>
            <Stack gap="sm">
              <FeaturePreview
                title="共读"
                description="以后可以放进同一本书、记录进度，也可以留下只属于你们的批注。"
                detail="书目、阅读进度与批注保存能力尚未接入；这里不会展示虚构数据。"
              />
              <FeaturePreview
                title="平行空间"
                description="一起写一个可以暂停、继续，也真正记得上次停在哪里的共同故事。"
                detail="故事存档与续写能力尚未接入；完成前不会提供无效的“继续故事”按钮。"
              />
            </Stack>
          </div>
        </Stack>
      </div>
    </RoomShell>
  );
}
