$ErrorActionPreference = "Stop"
$BaseUrl = if ($env:LIBRARY_API_URL) { $env:LIBRARY_API_URL } else { "http://127.0.0.1:8000" }
$CookieFile = Join-Path $PSScriptRoot "cookies.txt"

function Invoke-CurlJson {
  param(
    [string]$Url,
    [hashtable]$Body,
    [string]$CookieJar,
    [switch]$IncludeHeaders
  )

  $bodyFile = Join-Path ([System.IO.Path]::GetTempPath()) "library-api-$([guid]::NewGuid().ToString('N')).json"
  $json = ConvertTo-Json -InputObject $Body -Depth 5 -Compress
  $utf8 = New-Object System.Text.UTF8Encoding -ArgumentList $false
  [System.IO.File]::WriteAllText($bodyFile, $json, $utf8)

  $curlArgs = @("-sS", "-X", "POST", "-H", "Content-Type: application/json", "--data-binary", "@$bodyFile")
  if ($CookieJar) {
    $curlArgs += @("-b", $CookieJar, "-c", $CookieJar)
  }
  if ($IncludeHeaders) {
    $curlArgs = @("-i") + $curlArgs
  }

  try {
    $result = & curl.exe @curlArgs $Url
    if ($LASTEXITCODE -ne 0) {
      throw "curl.exe could not send request to $Url"
    }
    return ($result -join "`n")
  } finally {
    if (Test-Path $bodyFile) {
      Remove-Item -LiteralPath $bodyFile
    }
  }
}

try {
  Write-Host "`n1. Public book list (expected 200)"
  curl.exe -sS -i "$BaseUrl/api/books"

  Write-Host "`n2. Member loans without login (expected 401)"
  curl.exe -sS -i "$BaseUrl/api/me/loans"

  Write-Host "`n3. Librarian login (expected 200 and session cookie)"
  Invoke-CurlJson -Url "$BaseUrl/api/librarians/login" `
    -Body @{ email = "admin@library.com"; password = "admin12345" } `
    -CookieJar $CookieFile -IncludeHeaders

  Write-Host "`n4. Overdue loans as librarian (expected 200)"
  curl.exe -sS -i -b $CookieFile "$BaseUrl/api/reports/overdue"

  Write-Host "`n5. Check out sample copy 4 to member 1 (expected 201)"
  $CheckoutResponse = Invoke-CurlJson -Url "$BaseUrl/api/loans" `
    -Body @{ member_id = 1; copy_id = 4 } -CookieJar $CookieFile | ConvertFrom-Json
  if (-not $CheckoutResponse.loan_id) {
    throw "Checkout failed. Confirm sample data is loaded and copy 4 is available."
  }

  Write-Host "`n6. Check out the same copy again (expected 409)"
  Invoke-CurlJson -Url "$BaseUrl/api/loans" `
    -Body @{ member_id = 1; copy_id = 4 } -CookieJar $CookieFile -IncludeHeaders

  Write-Host "`n7. Check out sample copy 5 (expected 201)"
  $SecondCheckoutResponse = Invoke-CurlJson -Url "$BaseUrl/api/loans" `
    -Body @{ member_id = 1; copy_id = 5 } -CookieJar $CookieFile | ConvertFrom-Json
  if (-not $SecondCheckoutResponse.loan_id) {
    throw "Second checkout failed. Confirm sample copy 5 is available."
  }

  Write-Host "`n8. Try a fourth active loan (expected 409)"
  Invoke-CurlJson -Url "$BaseUrl/api/loans" `
    -Body @{ member_id = 1; copy_id = 6 } -CookieJar $CookieFile -IncludeHeaders

  Write-Host "`n9. Return sample copies (expected 200)"
  curl.exe -sS -i -X POST -b $CookieFile "$BaseUrl/api/loans/$($CheckoutResponse.loan_id)/return"
  curl.exe -sS -i -X POST -b $CookieFile "$BaseUrl/api/loans/$($SecondCheckoutResponse.loan_id)/return"

  Write-Host "`n10. Return overdue sample loan 2 (expected fine of 60)"
  curl.exe -sS -i -X POST -b $CookieFile "$BaseUrl/api/loans/2/return"

  Write-Host "`n11. Member login (expected token)"
  $LoginResponse = Invoke-CurlJson -Url "$BaseUrl/api/members/login" `
    -Body @{ email = "aisha@example.com"; password = "member12345" } | ConvertFrom-Json
  $MemberToken = $LoginResponse.access_token
  if (-not $MemberToken) {
    throw "Member login did not return a token. Check the API and sample data."
  }

  Write-Host "`n12. Member sees own loans (expected 200)"
  curl.exe -sS -i "$BaseUrl/api/me/loans" -H "Authorization: Bearer $MemberToken"

  Write-Host "`n13. Member tries to pay another member's fine (expected 404)"
  curl.exe -sS -i -X POST "$BaseUrl/api/fines/1/pay" -H "Authorization: Bearer $MemberToken"

  if ($env:PARTNER_API_KEY -and $env:PARTNER_API_SECRET) {
    Write-Host "`n14. Partner catalogue with credentials (expected 200)"
    curl.exe -sS -i "$BaseUrl/api/partner/books" `
      -H "X-API-Key: $env:PARTNER_API_KEY" `
      -H "X-API-Secret: $env:PARTNER_API_SECRET"
  } else {
    Write-Host "`nPartner check skipped. Set PARTNER_API_KEY and PARTNER_API_SECRET first."
  }
} finally {
  if (Test-Path $CookieFile) {
    Remove-Item -LiteralPath $CookieFile
  }
}
