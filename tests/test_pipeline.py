import io,sys,unittest,zipfile,tempfile
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).parents[1]))
from build import COLS,extract_source,prepare,quality_controls,run_aggregates,wilson

def fixture():
 rows=[]
 for i,(campaign,pdays,previous,y) in enumerate([(1,999,0,'no'),(2,10,1,'yes'),(3,0,1,'no'),(4,999,0,'no'),(5,999,0,'yes'),(6,999,0,'no'),(1,999,0,'no')]):
  rows.append([35,'admin.','single','high.school','no','yes','no','cellular','may','mon',100,campaign,pdays,previous,'success' if previous else 'nonexistent',1.1,93.9,-36.4,4.8,5191,y])
 return pd.DataFrame(rows,columns=COLS)

class PipelineTests(unittest.TestCase):
 def test_prepare_derives_bands_and_recency(self):
  d=prepare(fixture(),expected=None); self.assertEqual(d.contact_band.tolist(),['1','2','3','4-5','4-5','6+','1']); self.assertEqual(d.pdays_clean.notna().sum(),2); self.assertEqual(d.prior_contacted.sum(),2); self.assertEqual(d.loc[d.pdays!=999,'pdays_clean'].mean(),5)
 def test_rejects_bad_inputs(self):
  for c,v in [('y','maybe'),('contact','fax'),('campaign',0),('campaign',1.5),('age',0),('duration',float('inf'))]:
   r=fixture(); r.loc[0,c]=v
   with self.assertRaises(ValueError): prepare(r,expected=None)
  with self.assertRaises(ValueError): prepare(fixture().rename(columns={'age':'years'}),expected=None)
 def test_duplicates_controls(self):
  r=fixture(); c=quality_controls(r,prepare(r,expected=None)); self.assertEqual(c['exact_duplicate_rows'],1); self.assertEqual(c['duplicate_groups'],1); self.assertEqual(c['duplicate_affected_rows'],2)
 def test_wilson(self):
  lo,hi=wilson(1,4); self.assertAlmostEqual(lo,.0456,places=4); self.assertAlmostEqual(hi,.6994,places=4); self.assertEqual(wilson(0,0),(None,None))
  for a in [(1,0),(-1,4),(5,4)]:
   with self.assertRaises(ValueError): wilson(*a)
 def test_nested_extraction(self):
  csv=fixture().to_csv(sep=';',index=False).encode(); b=io.BytesIO()
  with zipfile.ZipFile(b,'w') as z: z.writestr('bank-additional/bank-additional-full.csv',csv); z.writestr('bank-additional/bank-additional-names.txt',b'names')
  o=io.BytesIO()
  with zipfile.ZipFile(o,'w') as z: z.writestr('bank-additional.zip',b.getvalue())
  with tempfile.TemporaryDirectory() as td:
   p=extract_source(o.getvalue(),Path(td)); self.assertTrue(p.exists()); self.assertTrue((Path(td)/'bank-additional-names.txt').exists())
 def test_sql_reconciliation(self):
  r=fixture(); d=prepare(r,expected=None); import sqlite3
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as td, patch('build.REPORTS',Path(td)), sqlite3.connect(':memory:') as cx:
   d.to_sql('observations',cx,index=False); out=run_aggregates(d,cx,Path(__file__).parents[1]/'sql')
   self.assertEqual(len(out),6)
   for path in Path(td).glob('*.csv'):
    t=pd.read_csv(path); self.assertEqual(int(t.records.sum()),len(d)); self.assertEqual(int(t.subscriptions.sum()),int(d.subscribed.sum()))
