# utils/alert_utils.py
import requests
import json

def send_dingtalk_alert(webhook_url: str, alerts: List[Dict]):
    """发送钉钉预警"""
    if not alerts:
        return
    
    content = "⚠️ AiStock 风控预警\n\n"
    for alert in alerts:
        content += f"• {alert['code']}: {alert['type']}\n  {alert['message']}\n\n"
    
    data = {
        "msgtype": "text",
        "text": {"content": content}
    }
    
    try:
        requests.post(webhook_url, json=data, timeout=10)
        print("✅ 钉钉预警已发送")
    except Exception as e:
        print(f"❌ 钉钉发送失败: {e}")