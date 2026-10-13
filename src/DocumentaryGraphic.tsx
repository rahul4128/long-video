import React from 'react';
import {
  AbsoluteFill,
  Easing,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { loadFont } from '@remotion/google-fonts/NotoSansDevanagari';

const {fontFamily} = loadFont();

export type GraphicSpec = {
  kind: 'question' | 'explainer_step' | 'key_point';
  label: string;
  step?: number;
  total?: number;
};

/** Text is quoted verbatim from verified narration, not AI-generated overlays.
 * A single gentle card at a genuinely useful story beat, CPU-only.
 * No falsified dates/maps/charts, no deity-face occlusion, no bottom subtitles overlap.
 */
export const DocumentaryGraphic: React.FC<{
  graphic: GraphicSpec;
  format: 'long' | 'shorts';
  maxFrames: number;
}> = ({graphic,format,maxFrames}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const shorts = format === 'shorts';
  const duration = Math.max(8,Math.min(maxFrames,Math.round(fps * 2.05)));
  const enter = interpolate(frame,[0,Math.max(4,Math.round(fps * 0.24))],[0,1],{
    easing:Easing.out(Easing.cubic),extrapolateLeft:'clamp',extrapolateRight:'clamp',
  });
  const exit = interpolate(frame,[Math.max(0,duration-8),duration],[1,0],{
    extrapolateLeft:'clamp',extrapolateRight:'clamp',
  });
  const visible = Math.max(0,Math.min(enter,exit));
  const isQuestion = graphic.kind === 'question';
  const explainer = graphic.kind === 'explainer_step' && !!graphic.total;
  const eyebrow = isQuestion ? 'एक जरूरी सवाल' : explainer ? 'समझिए, एक-एक करके' : 'ध्यान दें';
  const gold = '#F6D787';
  const accent = isQuestion ? '#FFCF5D' : '#A9D2F2';
  const cardTop = shorts ? 255 : 95;
  const cardWidth = shorts ? 755 : 780;
  const slide = interpolate(enter,[0,1],[-27,0]);
  const progress = Math.min(1,Math.max(0,(graphic.step || 0)/Math.max(1,graphic.total || 1)));
  if (!graphic.label.trim()) return null;
  return (
    <AbsoluteFill style={{zIndex:4,pointerEvents:'none'}}>
      <div style={{
        position:'absolute',top:cardTop,left:shorts?70:132,
        maxWidth:cardWidth,opacity:visible,
        transform:'translate3d('+slide+'px,0,0)',
        borderRadius:shorts?14:12,
        border:'1px solid rgba(255,246,218,0.26)',
        background:'linear-gradient(105deg,rgba(8,12,20,0.92),rgba(14,24,37,0.78))',
        boxShadow:'0 10px 32px rgba(0,0,0,0.28)',
        padding:shorts?'18px 28px 21px':'14px 25px 17px',
      }}>
        <div style={{fontFamily,fontWeight:750,fontSize:shorts?25:19,
          letterSpacing:1.2,color:accent,marginBottom:shorts?6:4}}>
          {eyebrow}{explainer ? '  '+graphic.step+'/'+graphic.total : ''}
        </div>
        <div style={{fontFamily,fontWeight:850,fontSize:shorts?41:37,
          lineHeight:1.25,color:'#FFF6E2',textShadow:'0 2px 6px rgba(0,0,0,.5)',
          maxWidth:cardWidth-70}}>
          {graphic.label}
        </div>
        {explainer && (
          <div style={{height:shorts?5:4,borderRadius:20,marginTop:shorts?13:10,
            background:'rgba(255,255,255,0.13)',width:shorts?620:670}}>
            <div style={{height:'100%',width:(progress*100)+'%',borderRadius:20,
              background:'linear-gradient(90deg,'+accent+','+gold+')'}}/>
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
