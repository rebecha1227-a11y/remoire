import os
from pathlib import Path
from playwright.sync_api import sync_playwright
ARTIFACTS=Path(__file__).resolve().parents[2]/'output'/'playwright'
ARTIFACTS.mkdir(parents=True,exist_ok=True)
FONT=os.environ.get('REMOIRE_TEST_FONT','/System/Library/Fonts/Supplemental/Georgia.ttf')
with sync_playwright() as p:
 b=p.chromium.launch(channel='chrome',headless=True)
 page=b.new_page(viewport={'width':430,'height':860})
 errors=[]
 page.on('pageerror',lambda error: errors.append(str(error)))
 page.add_init_script("localStorage.setItem('remoire_time_override','night')")
 page.goto('http://127.0.0.1:4175',wait_until='domcontentloaded')
 page.locator('.r-bubble').first.wait_for()
 page.wait_for_timeout(900)
 assert 'Noto Serif SC' in page.locator('.r-bubble').first.evaluate('(e)=>getComputedStyle(e).fontFamily')
 assert page.locator('button[title="复制"]').first.bounding_box()['width']==19
 offset=page.evaluate("()=>{const t=document.querySelector('.r-input'),b=document.querySelector('.r-mode-label'),r=t.getBoundingClientRect(),s=getComputedStyle(t);return r.y+parseFloat(s.paddingTop)+parseFloat(s.lineHeight)/2-b.getBoundingClientRect().y-b.clientHeight/2}")
 assert abs(offset)<1
 print('Default font, compact actions and composer alignment passed')
 page.screenshot(path=str(ARTIFACTS/'chat.png'))
 page.get_by_role('button',name='设置',exact=True).click()
 for color in ['#F8E85A','#A04480','#355A44']:
  page.evaluate("c=>window.dispatchEvent(new CustomEvent('tweak-update',{detail:{accentColor:c}}))",color)
  page.wait_for_timeout(250)
  for knob in page.get_by_role('switch').locator('span').all():
   assert knob.evaluate('(e)=>getComputedStyle(e).backgroundColor')=='rgb(255, 255, 255)'
 print('White switch thumb: 3 theme colors passed')
 page.get_by_role('button',name='字体 为聊天、纸条、日记等分别设置').click()
 with page.expect_file_chooser() as chooser:
  page.get_by_role('button',name='上传',exact=True).first.click()
 chooser.value.set_files(FONT)
 page.wait_for_function("document.fonts.check('16px RemoireCustomChat') && document.documentElement.style.getPropertyValue('--font-chat').includes('RemoireCustomChat')")
 page.get_by_role('button',name='聊天',exact=True).click()
 assert page.locator('.r-bubble').first.evaluate('(e)=>getComputedStyle(e).fontFamily').startswith('RemoireCustomChat')
 assert page.locator('.r-input').evaluate('(e)=>getComputedStyle(e).fontFamily').startswith('RemoireCustomChat')
 page.reload(wait_until='domcontentloaded')
 page.locator('.r-bubble').first.wait_for()
 page.wait_for_function("document.documentElement.style.getPropertyValue('--font-chat').includes('RemoireCustomChat')")
 print('Real font upload: bubble, composer and reload passed')
 page.get_by_role('button',name='设置',exact=True).click()
 page.get_by_role('button',name='字体 为聊天、纸条、日记等分别设置').click()
 page.get_by_role('button',name='恢复默认',exact=True).click()
 page.get_by_role('button',name='聊天',exact=True).click()
 page.wait_for_function("getComputedStyle(document.querySelector('.r-bubble')).fontFamily.includes('Noto Serif SC')")
 print('Restore default font passed')
 page.get_by_role('button',name='玩乐',exact=True).click()
 page.get_by_text('挪威的森林',exact=True).wait_for()
 assert page.get_by_text('筹备中',exact=True).count()==2
 page.wait_for_timeout(700)
 page.screenshot(path=str(ARTIFACTS/'play.png'))
 page.get_by_role('button',name='进入平行空间预览').click()
 page.get_by_role('button',name='筹备中 · 继续故事').wait_for()
 assert page.get_by_role('button',name='筹备中 · 继续故事').is_disabled()
 page.get_by_role('button',name='← 回到现实').click()
 print('Original reading and parallel preview restored, entry/back passed')
 page.get_by_role('button',name='打开 Connie 的生活日志和碎碎念').click()
 page.get_by_text('本地虚构生活日志，仅用于视觉预览',exact=True).wait_for()
 page.get_by_role('button',name='上个月').click()
 page.get_by_role('button',name='下个月').click()
 page.get_by_role('button',name='',exact=True).first.click()
 page.get_by_text('挪威的森林',exact=True).wait_for()
 assert not errors, errors
 print('Connie timeline fixture: entry, calendar, logs and back passed')
 page.get_by_role('button',name='日记',exact=True).click()
 page.get_by_role('button',name='打开静儿的日记').click()
 page.get_by_role('button',name='下一页').click()
 page.wait_for_timeout(1000)
 comment=page.get_by_role('button',name='留下这句话')
 assert comment.evaluate('(e)=>getComputedStyle(e).color')=='rgb(61, 50, 41)'
 page.reload(wait_until='domcontentloaded')
 page.get_by_role('button',name='日记',exact=True).click()
 page.get_by_role('button',name='写今天的日记…').click()
 title=page.get_by_placeholder('标题（可留空）'); body=page.get_by_placeholder('今天…')
 body.fill('视觉回归示例'); title.fill('本地示例')
 page.wait_for_timeout(400)
 page.evaluate("window.heightMutations=0;new MutationObserver(ms=>window.heightMutations+=ms.length).observe(document.body,{attributes:true,attributeFilter:['style']})")
 body.focus(); title.focus(); page.wait_for_timeout(450)
 assert page.evaluate('window.heightMutations')==0
 assert body.evaluate('(e)=>getComputedStyle(e).color')=='rgb(61, 50, 41)'
 assert page.get_by_role('button',name='保存',exact=True).evaluate('(e)=>getComputedStyle(e).color')=='rgb(61, 50, 41)'
 page.screenshot(path=str(ARTIFACTS/'diary.png'))
 print('Diary editor, comment contrast, and focus-switch stability passed')
 assert not errors, errors
 b.close()
