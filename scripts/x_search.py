#!/usr/bin/env python3
import urllib.request, urllib.parse, json, sys

AUTH_TOKEN = '3b54a9d0ca49ad313117585f790b4d18555665e4'
CT0 = '441677cc301d8e8221dd112d97c7b064afc260b292b783b7a0134dcaac7f78d0525100105babdf6923dd10e713e135877063aba192d7f8ad3a3bc21346a35b003b7b45c17c1f9bd26833bf6a4909ba64'
TWID = 'u%3D1424714686138703872'
CF_BM = 'nG0o5L8x5a3Nl68D1jlsbEL172PAnrzuacv554xXJtw-1784093354.8932664-1.0.1.1-I09gtx8UiDgeFaRcz8CHaLMls1Hc9WkrkKAkICoBeJ78O0mw5JCnXlnVfUDVvXtYm7eNi12kIKa.wzABQZ41.Gdfj7QoEjxuaeQ4M7rmGX8F6I1CeBp2m6uxS5A4s8WY'
BEARER = 'AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA'
QID = 'hz_94eVAtrtQo_vO3my7Rw'
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'

FS = ["rweb_video_screen_enabled","rweb_cashtags_enabled","profile_label_improvements_pcf_label_in_post_enabled","responsive_web_profile_redirect_enabled","rweb_tipjar_consumption_enabled","verified_phone_label_enabled","creator_subscriptions_tweet_preview_api_enabled","responsive_web_graphql_timeline_navigation_enabled","responsive_web_graphql_skip_user_profile_image_extensions_enabled","premium_content_api_read_enabled","communities_web_enable_tweet_community_results_fetch","c9s_tweet_anatomy_moderator_badge_enabled","responsive_web_grok_analyze_button_fetch_trends_enabled","responsive_web_grok_analyze_post_followups_enabled","rweb_cashtags_composer_attachment_enabled","responsive_web_jetfuel_frame","responsive_web_grok_share_attachment_enabled","responsive_web_grok_annotations_enabled","articles_preview_enabled","responsive_web_edit_tweet_api_enabled","rweb_conversational_replies_downvote_enabled","graphql_is_translatable_rweb_tweet_is_translatable_enabled","view_counts_everywhere_api_enabled","longform_notetweets_consumption_enabled","responsive_web_twitter_article_tweet_consumption_enabled","content_disclosure_indicator_enabled","content_disclosure_ai_generated_indicator_enabled","responsive_web_grok_show_grok_translated_post","responsive_web_grok_analysis_button_from_backend","post_ctas_fetch_enabled","freedom_of_speech_not_reach_fetch_enabled","standardized_nudges_misinfo","tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled","longform_notetweets_rich_text_read_enabled","longform_notetweets_inline_media_enabled","responsive_web_grok_image_annotation_enabled","responsive_web_grok_imagine_annotation_enabled","responsive_web_grok_community_note_auto_translation_is_enabled","responsive_web_enhance_cards_enabled"]
# default all True (aman)
FEATURES = {k: True for k in FS}
# selected False (biar match default runtime)
for k in ["rweb_video_screen_enabled","verified_phone_label_enabled","premium_content_api_read_enabled","responsive_web_grok_analyze_button_fetch_trends_enabled","responsive_web_grok_show_grok_translated_post","responsive_web_enhance_cards_enabled","payments_enabled"]:
    if k in FEATURES: FEATURES[k] = False

FT = {"withPayments": False, "withAuxiliaryUserLabels": True, "withArticleRichContentState": True, "withArticlePlainText": False, "withArticleSummaryText": False, "withArticleVoiceOver": False, "withGrokAnalyze": False, "withDisallowedReplyControls": False}

def search(query, product='Latest', count=40, cursor=None):
    cookie = f'auth_token={AUTH_TOKEN}; ct0={CT0}; twid={TWID}; __cf_bm={CF_BM}'
    headers = {'cookie': cookie,'user-agent': UA,'x-twitter-active-user':'yes','x-twitter-client-language':'en','x-csrf-token': CT0,'authorization': f'Bearer {BEARER}','accept':'*/*','referer':'https://x.com/search','x-twitter-auth-type':'OAuth2Session'}
    variables = {"rawQuery": query, "count": count, "querySource": "typed_query", "product": product}
    if cursor: variables["cursor"] = cursor
    params = urllib.parse.urlencode({'variables': json.dumps(variables), 'features': json.dumps(FEATURES), 'fieldToggles': json.dumps(FT)})
    url = f'https://x.com/i/api/graphql/{QID}/SearchTimeline?{params}'
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f'HTTP {e.code}: {e.read().decode()[:300]}', file=sys.stderr)
        return None

def extract(data):
    out = []
    if not data: return out
    try:
        instr = data['data']['search_by_raw_query']['search_timeline']['timeline']['instructions']
    except (KeyError, TypeError):
        return out
    for ins in instr:
        entries = ins.get('entries', [])
        if not entries and ins.get('entry'):
            entries = [ins['entry']]
        for e in entries:
            if not e: continue
            content = e.get('content', {})
            item = content.get('itemContent')
            if not item: continue
            tr = item.get('tweet_results', {}).get('result')
            if not tr: continue
            if tr.get('__typename') == 'TweetWithVisibilityResults':
                tr = tr.get('tweet', tr)
            legacy = tr.get('legacy', {})
            core = tr.get('core', {}).get('user_results', {}).get('result', {})
            ul = core.get('legacy', {})
            uc = core.get('core', {})
            screen = uc.get('screen_name') or ul.get('screen_name', '?')
            name = uc.get('name') or ul.get('name', '?')
            text = legacy.get('full_text', '')
            tid = tr.get('rest_id', legacy.get('id_str', ''))
            views = tr.get('views', {}).get('count', 0)
            out.append({'id': tid, 'user': screen, 'name': name, 'text': text, 'created': legacy.get('created_at',''), 'fav': legacy.get('favorite_count',0), 'rt': legacy.get('retweet_count',0), 'reply': legacy.get('reply_count',0), 'views': int(views) if views else 0, 'url': f'https://x.com/{screen}/status/{tid}'})
    return out

if __name__ == '__main__':
    q = sys.argv[1] if len(sys.argv) > 1 else 'bug bounty'
    p = sys.argv[2] if len(sys.argv) > 2 else 'Latest'
    print(f'# Q: {q} | product: {p}', file=sys.stderr)
    d = search(q, product=p)
    ts = extract(d)
    print(f'# {len(ts)} tweets', file=sys.stderr)
    for t in ts:
        print(json.dumps(t, ensure_ascii=False))
