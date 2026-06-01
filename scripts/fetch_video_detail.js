#!/usr/bin/env node
// 提取单条抖音视频的元数据 + 视频下载地址
// 用法: node fetch_video_detail.js <aweme_id>
// 输出: JSON { title, desc, tags, videoSrc, authorName, followers, likes, comments, shares, publishDate }

const { chromium } = require('playwright-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');
chromium.use(StealthPlugin());

const AWEME_ID = process.argv[2];
if (!AWEME_ID) { console.error('用法: node fetch_video_detail.js <aweme_id>'); process.exit(1); }

const COOKIE_FILE = path.join(__dirname, '..', '..', 'douyin-search', 'scripts', 'cookie.txt');
const COOKIE_RAW = fs.readFileSync(COOKIE_FILE, 'utf-8').trim();

const LOGIN_NAMES = new Set([
  'sessionid','sessionid_ss','sid_guard','sid_tt','uid_tt','uid_tt_ss',
  'passport_csrf_token','passport_csrf_token_default','passport_auth_mix_state',
  'passport_assist_user','sid_ucp_v1','ssid_ucp_v1','session_tlb_tag',
  'is_staff_user','has_biz_token','login_time','IsDouyinActive','n_mh','odin_tt'
]);

function parseCookies(raw) {
  return raw.split('; ')
    .filter(p => LOGIN_NAMES.has(p.split('=')[0].trim()) || true)  // 保留所有cookie
    .map(p => {
      const idx = p.indexOf('=');
      return { name: p.substring(0, idx).trim(), value: p.substring(idx + 1), domain: '.douyin.com', path: '/' };
    });
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
  });
  await context.addCookies(parseCookies(COOKIE_RAW));

  const page = await context.newPage();
  const url = `https://www.douyin.com/video/${AWEME_ID}`;

  console.error(`⏳ 打开视频页面: ${url}`);
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });

  // 等视频元素
  try {
    await page.waitForSelector('video', { timeout: 15000 });
    console.error('✅ 视频元素已加载');
  } catch {
    console.error('⚠️ 未检测到video元素');
  }

  await page.waitForTimeout(5000);

  // 提取所有数据
  const data = await page.evaluate(() => {
    const video = document.querySelector('video');
    const videoSrc = video?.currentSrc || video?.src || '';
    const h1 = document.querySelector('h1');
    const fullTitle = h1?.textContent?.trim() || '';
    const tags = [...document.querySelectorAll('h1 a')].map(a => a.textContent?.trim()).filter(t => t.startsWith('#'));
    
    // 作者
    const authorEl = document.querySelector('[data-e2e="user-info"]');
    const authorName = authorEl?.querySelector('span')?.textContent?.trim() || '';
    const followerEl = authorEl?.querySelector('[data-e2e="follower-count"]');
    const followers = followerEl?.textContent?.trim() || '';
    
    // 互动
    const likes = document.querySelector('[data-e2e="like-count"]')?.textContent?.trim() || '';
    const comments = document.querySelector('[data-e2e="comment-count"]')?.textContent?.trim() || '';
    const shares = document.querySelector('[data-e2e="share-count"]')?.textContent?.trim() || '';
    const publishDate = document.querySelector('[data-e2e="publish-time"]')?.textContent?.trim() || '';

    return { fullTitle, videoSrc, authorName, followers, likes, comments, shares, publishDate, tags };
  });

  console.log(JSON.stringify(data, null, 2));
  await browser.close();
  process.exit(0);
})();
