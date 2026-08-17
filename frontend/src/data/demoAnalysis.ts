import type { AnalysisResult } from '../types/analysis'

const emptyGeoJson = {
  type: 'FeatureCollection' as const,
  features: []
}

export const demoAnalysis: AnalysisResult = {
  analysisId: 'demo-taipei-001',
  status: 'IMPROVEMENT_PROPOSED',
  location: { latitude: 25.033, longitude: 121.5654 },
  bounds: {
    south: 25.0321,
    west: 121.5644,
    north: 25.0339,
    east: 121.5664
  },
  intersectionType: 'ORTHOGONAL',
  overallScore: 58,
  problemSummary:
    '此路口的行人穿越距離偏長，轉角等候空間不足，車道進入路口後缺少清楚的續進導引。右轉車流與行人穿越動線重疊，形成需要優先處理的衝突。',
  improvementSummary:
    '方案將行穿線退縮並縮短穿越距離，於中央增設行人庇護空間，同時外推轉角、調整停止線與車道導引，使轉彎車能更早看見行人並以較低速度通過。',
  findings: [
    {
      category: 'crosswalk',
      title: '穿越距離與轉彎衝突偏高',
      description: '東西向行穿線跨越範圍較長，且靠近右轉車主要行駛軌跡，增加行人暴露時間。',
      severity: 'HIGH',
      score: 48,
      evidence_feature_ids: ['crosswalk-east-west', 'road-south'],
      recommendation: '退縮行穿線並加入中央庇護空間，讓轉彎車在衝突前取得更完整視距。'
    },
    {
      category: 'sidewalk',
      title: '轉角停等空間不足',
      description: '轉角人行空間收窄，行人停等位置與車道邊界距離有限。',
      severity: 'MEDIUM',
      score: 61,
      evidence_feature_ids: ['sidewalk-northwest', 'sidewalk-southwest'],
      recommendation: '外推人行道轉角並整理無障礙銜接，形成清楚的等候與轉向空間。'
    },
    {
      category: 'lane_marking',
      title: '路口內車道導引不連續',
      description: '多車道進入路口後缺少續進導引，可能造成行車軌跡偏移與不必要的交織。',
      severity: 'MEDIUM',
      score: 65,
      evidence_feature_ids: ['lane-northbound', 'lane-southbound'],
      recommendation: '補上必要的續進導引並後移停止線，讓行車與行人空間更容易辨識。'
    }
  ],
  matchedCases: [
    {
      id: 'taipei-zhongxiao-jinshan',
      title: '忠孝東路二段與金山南路口改善',
      location: '臺北市',
      summary: '透過行穿線退縮、增設庇護島、縮小轉角半徑與拓寬停等空間改善行人安全。',
      sourceUrl:
        'https://www.motc.gov.tw/ch/app/data/view?id=14&module=news&serno=e670db95-a236-48ec-af1f-cc56ec803d9b',
      matchReason: '同樣具有穿越距離、轉彎衝突與轉角空間問題',
      score: 0.91
    },
    {
      id: 'reno-wells-avenue',
      title: 'Wells Avenue Road Diet',
      location: 'Reno, Nevada',
      summary: '透過車道重新配置、自行車道與庇護島，降低道路複雜度並改善行人穿越。',
      sourceUrl:
        'https://highways.dot.gov/safety/other/road-diets/road-diet-case-studies/reno-nevada-wells-avenue',
      matchReason: '以庇護空間與車道配置降低衝突的國外案例',
      score: 0.78
    }
  ],
  originalGeojson: emptyGeoJson,
  enrichedGeojson: emptyGeoJson,
  redesignedGeojson: emptyGeoJson,
  sourceImage: { mimeType: 'image/svg+xml', dataUrl: '/demo-before.svg' },
  renderedImage: { mimeType: 'image/svg+xml', dataUrl: '/demo-after.svg' },
  metadata: {
    demo: true,
    evidenceCoverage: '6/8',
    processingTimeSeconds: 52,
    dataSources: ['OpenStreetMap', '衛星影像', 'Gemini 視覺辨識']
  }
}
