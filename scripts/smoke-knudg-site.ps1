param(
  [Parameter(Mandatory = $true)]
  [string]$BaseUrl
)

$ErrorActionPreference = "Stop"

function Assert-Equal {
  param(
    [string]$Name,
    $Actual,
    $Expected
  )

  if ($Actual -ne $Expected) {
    throw "$Name expected '$Expected' but got '$Actual'"
  }
}

function Assert-Match {
  param(
    [string]$Name,
    [string]$Actual,
    [string]$Pattern
  )

  if ($Actual -notmatch $Pattern) {
    throw "$Name did not match '$Pattern'"
  }
}

function Assert-NoMatch {
  param(
    [string]$Name,
    [string]$Actual,
    [string]$Pattern
  )

  if ($Actual -match $Pattern) {
    throw "$Name unexpectedly matched '$Pattern'"
  }
}

$ExpectedCsp = "default-src 'self'; script-src 'none'; connect-src 'none'; img-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'; upgrade-insecure-requests"
$ExpectedPermissionsPolicy = "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()"
$ExpectedCacheControl = "public, max-age=0, must-revalidate, no-transform"
$EnglishSentinel = "self-hostable worklog for coding agents"
$JapaneseSentinel = -join ([char[]](0x67B6, 0x7A7A, 0x4F8B))
$Japanese404Sentinel = -join ([char[]](0x3053, 0x306E, 0x30DA, 0x30FC, 0x30B8, 0x306F, 0x8868, 0x793A, 0x3067, 0x304D, 0x307E, 0x305B, 0x3093))
$ChineseSentinel = -join ([char[]](0x865A, 0x6784, 0x793A, 0x4F8B))
$Chinese404Sentinel = -join ([char[]](0x8FD9, 0x4E2A, 0x9875, 0x9762, 0x65E0, 0x6CD5, 0x663E, 0x793A))

function Assert-SecurityHeaders {
  param(
    [string]$Name,
    $Headers
  )

  Assert-Equal "$Name CSP" $Headers["Content-Security-Policy"] $ExpectedCsp
  Assert-NoMatch "$Name CSP unsafe-inline" $Headers["Content-Security-Policy"] "unsafe-inline|unsafe-eval"
  Assert-Equal "$Name cache-control" $Headers["Cache-Control"] $ExpectedCacheControl
  Assert-Equal "$Name nosniff" $Headers["X-Content-Type-Options"] "nosniff"
  Assert-Equal "$Name frame policy" $Headers["X-Frame-Options"] "DENY"
  Assert-Equal "$Name referrer policy" $Headers["Referrer-Policy"] "strict-origin-when-cross-origin"
  Assert-Equal "$Name permissions policy" $Headers["Permissions-Policy"] $ExpectedPermissionsPolicy
  Assert-Equal "$Name HSTS" $Headers["Strict-Transport-Security"] "max-age=31536000"
  Assert-NoMatch "$Name CORS wildcard" $Headers["Access-Control-Allow-Origin"] "\*"
}

function Request-Http {
  param(
    [string]$Uri,
    [switch]$AllowError
  )

  $request = [System.Net.WebRequest]::Create($Uri)
  $request.UserAgent = "knudg-smoke"

  try {
    $response = $request.GetResponse()
  } catch {
    if (-not $AllowError) {
      throw
    }

    $webException = $_.Exception
    if ($webException.InnerException) {
      $webException = $webException.InnerException
    }

    if ($webException.Response) {
      $response = $webException.Response
    } else {
      throw
    }
  }

  try {
    $stream = $response.GetResponseStream()
    $reader = [IO.StreamReader]::new($stream, [Text.Encoding]::UTF8)
    return [pscustomobject]@{
      StatusCode = [int]$response.StatusCode
      Content = $reader.ReadToEnd()
      Headers = $response.Headers
    }
  } finally {
    if ($response) {
      $response.Close()
    }
  }
}

$homeResp = Request-Http "$BaseUrl/"
Assert-Equal "home status" $homeResp.StatusCode 200
Assert-SecurityHeaders "home" $homeResp.Headers
Assert-Match "home lang" $homeResp.Content '<html lang="en">'
Assert-Match "home canonical" $homeResp.Content '<link rel="canonical" href="https://knudg\.com/">'
Assert-Match "home en alternate" $homeResp.Content '<link rel="alternate" hreflang="en" href="https://knudg\.com/">'
Assert-Match "home ja alternate" $homeResp.Content '<link rel="alternate" hreflang="ja" href="https://knudg\.com/ja/">'
Assert-Match "home zh alternate" $homeResp.Content '<link rel="alternate" hreflang="zh-CN" href="https://knudg\.com/zh-cn/">'
Assert-Match "home default alternate" $homeResp.Content '<link rel="alternate" hreflang="x-default" href="https://knudg\.com/">'
Assert-Match "home body" $homeResp.Content ([regex]::Escape($EnglishSentinel))
Assert-NoMatch "home scripts" $homeResp.Content "<script\b"
Assert-NoMatch "home analytics beacon" $homeResp.Content "cloudflareinsights|/cdn-cgi/rum|beacon\.min\.js"

$ja = Request-Http "$BaseUrl/ja/"
Assert-Equal "ja status" $ja.StatusCode 200
Assert-SecurityHeaders "ja" $ja.Headers
Assert-Match "ja lang" $ja.Content '<html lang="ja">'
Assert-Match "ja canonical" $ja.Content '<link rel="canonical" href="https://knudg\.com/ja/">'
Assert-Match "ja en alternate" $ja.Content '<link rel="alternate" hreflang="en" href="https://knudg\.com/">'
Assert-Match "ja self alternate" $ja.Content '<link rel="alternate" hreflang="ja" href="https://knudg\.com/ja/">'
Assert-Match "ja zh alternate" $ja.Content '<link rel="alternate" hreflang="zh-CN" href="https://knudg\.com/zh-cn/">'
Assert-Match "ja default alternate" $ja.Content '<link rel="alternate" hreflang="x-default" href="https://knudg\.com/">'
Assert-Match "ja body" $ja.Content ([regex]::Escape($JapaneseSentinel))
Assert-NoMatch "ja scripts" $ja.Content "<script\b"
Assert-NoMatch "ja analytics beacon" $ja.Content "cloudflareinsights|/cdn-cgi/rum|beacon\.min\.js"

$zh = Request-Http "$BaseUrl/zh-cn/"
Assert-Equal "zh-cn status" $zh.StatusCode 200
Assert-SecurityHeaders "zh-cn" $zh.Headers
Assert-Match "zh-cn lang" $zh.Content '<html lang="zh-CN">'
Assert-Match "zh-cn canonical" $zh.Content '<link rel="canonical" href="https://knudg\.com/zh-cn/">'
Assert-Match "zh-cn en alternate" $zh.Content '<link rel="alternate" hreflang="en" href="https://knudg\.com/">'
Assert-Match "zh-cn ja alternate" $zh.Content '<link rel="alternate" hreflang="ja" href="https://knudg\.com/ja/">'
Assert-Match "zh-cn self alternate" $zh.Content '<link rel="alternate" hreflang="zh-CN" href="https://knudg\.com/zh-cn/">'
Assert-Match "zh-cn default alternate" $zh.Content '<link rel="alternate" hreflang="x-default" href="https://knudg\.com/">'
Assert-Match "zh-cn body" $zh.Content ([regex]::Escape($ChineseSentinel))
Assert-NoMatch "zh-cn scripts" $zh.Content "<script\b"
Assert-NoMatch "zh-cn analytics beacon" $zh.Content "cloudflareinsights|/cdn-cgi/rum|beacon\.min\.js"

$css = Request-Http "$BaseUrl/styles.css?v=layout-20260602b"
Assert-Equal "css status" $css.StatusCode 200
Assert-Match "css content-type" $css.Headers["Content-Type"] "text/css"
Assert-SecurityHeaders "css" $css.Headers

$missing = Request-Http "$BaseUrl/missing-smoke" -AllowError
Assert-Equal "missing status" $missing.StatusCode 404
Assert-Match "missing body" $missing.Content "This page is not available"
Assert-Match "missing noindex" $missing.Content '<meta name="robots" content="noindex">'
Assert-Match "missing css absolute" $missing.Content '<link rel="stylesheet" href="/styles\.css\?v=layout-20260602b">'
Assert-SecurityHeaders "missing" $missing.Headers

$jaMissing = Request-Http "$BaseUrl/ja/missing-smoke" -AllowError
Assert-Equal "ja missing status" $jaMissing.StatusCode 404
Assert-Match "ja missing body" $jaMissing.Content '<html lang="ja">'
Assert-Match "ja missing localized body" $jaMissing.Content ([regex]::Escape($Japanese404Sentinel))
Assert-Match "ja missing noindex" $jaMissing.Content '<meta name="robots" content="noindex">'
Assert-Match "ja missing css absolute" $jaMissing.Content '<link rel="stylesheet" href="/styles\.css\?v=layout-20260602b">'
Assert-SecurityHeaders "ja missing" $jaMissing.Headers

$zhMissing = Request-Http "$BaseUrl/zh-cn/missing-smoke" -AllowError
Assert-Equal "zh-cn missing status" $zhMissing.StatusCode 404
Assert-Match "zh-cn missing body" $zhMissing.Content '<html lang="zh-CN">'
Assert-Match "zh-cn missing localized body" $zhMissing.Content ([regex]::Escape($Chinese404Sentinel))
Assert-Match "zh-cn missing noindex" $zhMissing.Content '<meta name="robots" content="noindex">'
Assert-Match "zh-cn missing css absolute" $zhMissing.Content '<link rel="stylesheet" href="/styles\.css\?v=layout-20260602b">'
Assert-NoMatch "zh-cn missing wrong body class" $zhMissing.Content '<body class="zh-page ja-page">'
Assert-SecurityHeaders "zh-cn missing" $zhMissing.Headers

$deepMissing = Request-Http "$BaseUrl/deep/missing-smoke" -AllowError
Assert-Equal "deep missing status" $deepMissing.StatusCode 404
Assert-Match "deep missing css absolute" $deepMissing.Content '<link rel="stylesheet" href="/styles\.css\?v=layout-20260602b">'
Assert-SecurityHeaders "deep missing" $deepMissing.Headers

$jaDeepMissing = Request-Http "$BaseUrl/ja/deep/missing-smoke" -AllowError
Assert-Equal "ja deep missing status" $jaDeepMissing.StatusCode 404
Assert-Match "ja deep missing body" $jaDeepMissing.Content '<html lang="ja">'
Assert-Match "ja deep missing css absolute" $jaDeepMissing.Content '<link rel="stylesheet" href="/styles\.css\?v=layout-20260602b">'
Assert-SecurityHeaders "ja deep missing" $jaDeepMissing.Headers

$zhDeepMissing = Request-Http "$BaseUrl/zh-cn/deep/missing-smoke" -AllowError
Assert-Equal "zh-cn deep missing status" $zhDeepMissing.StatusCode 404
Assert-Match "zh-cn deep missing body" $zhDeepMissing.Content '<html lang="zh-CN">'
Assert-Match "zh-cn deep missing css absolute" $zhDeepMissing.Content '<link rel="stylesheet" href="/styles\.css\?v=layout-20260602b">'
Assert-NoMatch "zh-cn deep missing wrong body class" $zhDeepMissing.Content '<body class="zh-page ja-page">'
Assert-SecurityHeaders "zh-cn deep missing" $zhDeepMissing.Headers

function Assert-StaticPreviewBody {
  param(
    [string]$Name,
    [string]$Content
  )

  Assert-NoMatch "$Name scripts" $Content "<script\b"
  Assert-NoMatch "$Name forms" $Content "<form\b"
  Assert-NoMatch "$Name buttons" $Content "<button\b"
  Assert-NoMatch "$Name submit controls" $Content '<input\b[^>]+type=["'']?(submit|image|button)'
  Assert-NoMatch "$Name formaction" $Content "formaction="
  Assert-NoMatch "$Name button roles" $Content 'role=["'']button["'']'
  Assert-NoMatch "$Name mailto links" $Content 'href=["'']mailto:'
  Assert-NoMatch "$Name tel links" $Content 'href=["'']tel:'
  Assert-NoMatch "$Name disallowed external anchors" $Content '<a\b[^>]+href=["''](?!(?:https://github\.com/1kgofpastaeveryday/knudg/?)(?:["'']|#|\?))(?:https?:)?//'
  Assert-NoMatch "$Name iframes" $Content "<iframe\b"
  Assert-NoMatch "$Name object embeds" $Content "<(object|embed)\b"
  Assert-NoMatch "$Name media embeds" $Content "<(video|audio|source|picture)\b"
  Assert-NoMatch "$Name external resources" $Content '<script\b[^>]+src=["''](?:https?:)?//|<img\b[^>]+src=["''](?:https?:)?//|<link\b[^>]+rel=["''][^"'']*(stylesheet|preload|icon|manifest)[^"'']*["''][^>]+href=["''](?:https?:)?//'
}

Assert-StaticPreviewBody "home body" $homeResp.Content
Assert-StaticPreviewBody "ja body" $ja.Content
Assert-StaticPreviewBody "zh-cn body" $zh.Content
Assert-StaticPreviewBody "missing body" $missing.Content
Assert-StaticPreviewBody "ja missing body" $jaMissing.Content
Assert-StaticPreviewBody "zh-cn missing body" $zhMissing.Content
Assert-StaticPreviewBody "deep missing body" $deepMissing.Content
Assert-StaticPreviewBody "ja deep missing body" $jaDeepMissing.Content
Assert-StaticPreviewBody "zh-cn deep missing body" $zhDeepMissing.Content

$www = $null
try {
  $www = Resolve-DnsName "www.knudg.com" -ErrorAction Stop
} catch {
  $message = $_.Exception.Message
  $id = $_.FullyQualifiedErrorId
  if ($message -notmatch "DNS name does not exist|DNS_ERROR_RCODE_NAME_ERROR|Non-existent domain|NXDOMAIN" -and
      $id -notmatch "DNS_ERROR_RCODE_NAME_ERROR|DNSNameDoesNotExist") {
    throw
  }
}

if ($www) {
  throw "www.knudg.com unexpectedly resolves; define redirect/route policy before leaving it live"
}

Write-Output "knudg.com smoke checks passed"
