import { createInterface } from 'node:readline';

const WA_ACCESS_TOKEN = process.env.WA_ACCESS_TOKEN;
const WA_PHONE_NUMBER_ID = process.env.WA_PHONE_NUMBER_ID;
const API_VERSION = 'v25.0';
const BASE = `https://graph.facebook.com/${API_VERSION}/${WA_PHONE_NUMBER_ID}`;

if (!WA_ACCESS_TOKEN || !WA_PHONE_NUMBER_ID) {
  console.error('ERROR: Missing secrets. Ensure WA_ACCESS_TOKEN and WA_PHONE_NUMBER_ID are set.');
  process.exit(1);
}

const headers = {
  'Authorization': `Bearer ${WA_ACCESS_TOKEN}`,
  'Content-Type': 'application/json',
};

function ask(question) {
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => {
    rl.question(question, (answer) => {
      rl.close();
      resolve(answer.trim());
    });
  });
}

async function apiCall(method, url, body) {
  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(url, opts);
  const data = await res.json();
  if (!res.ok) {
    const err = data?.error;
    if (err) {
      const code = err.code || res.status;
      const msg = err.error_user_msg || err.message || JSON.stringify(err);
      if (code === 136025) return { already_registered: true, raw: data };
      throw new Error(`[${code}] ${msg}`);
    }
    throw new Error(`HTTP ${res.status}: ${JSON.stringify(data)}`);
  }
  return data;
}

async function main() {
  console.log('=== WhatsApp Cloud API – Phone Registration ===\n');

  console.log('Step 1: Requesting verification code via SMS (language: he)...');
  try {
    const codeRes = await apiCall('POST', `${BASE}/request_code`, {
      messaging_product: 'whatsapp',
      code_method: 'SMS',
      language: 'he',
    });
    if (codeRes.already_registered) {
      console.log('Phone number appears to already be registered. Checking status...');
    } else {
      console.log('SMS code sent successfully.\n');
    }
  } catch (e) {
    if (e.message.includes('already registered') || e.message.includes('136025')) {
      console.log('Phone number is already registered! Checking status...');
    } else {
      console.error(`Failed to request code: ${e.message}`);
      console.error('Possible fixes: check WA_ACCESS_TOKEN permissions, or verify the phone number ID.');
      process.exit(1);
    }
  }

  const pin = await ask('Enter the 6-digit PIN from the SMS you received: ');

  if (!/^\d{6}$/.test(pin)) {
    console.error('ERROR: PIN must be exactly 6 digits.');
    process.exit(1);
  }

  console.log('\nStep 2: Registering phone number...');
  try {
    const regRes = await apiCall('POST', `${BASE}/register`, {
      messaging_product: 'whatsapp',
      pin: pin,
    });
    console.log('Registration response:', JSON.stringify(regRes, null, 2));
  } catch (e) {
    if (e.message.includes('incorrect') || e.message.includes('wrong')) {
      console.error(`Registration failed – wrong PIN: ${e.message}`);
    } else if (e.message.includes('permission')) {
      console.error(`Registration failed – missing permissions: ${e.message}`);
    } else {
      console.error(`Registration failed: ${e.message}`);
    }
    process.exit(1);
  }

  console.log('\nStep 3: Checking registration status...');
  try {
    const statusRes = await apiCall(
      'GET',
      `${BASE}?fields=verified_name,code_verification_status,quality_rating,status`,
      null,
    );
    console.log('\n=== Phone number registered ===');
    console.log(`  verified_name: ${statusRes.verified_name || 'N/A'}`);
    console.log(`  code_verification_status: ${statusRes.code_verification_status || 'N/A'}`);
    console.log(`  quality_rating: ${statusRes.quality_rating || 'N/A'}`);
    console.log(`  status: ${statusRes.status || 'N/A'}`);
  } catch (e) {
    console.log('Could not fetch status (may need additional permissions):', e.message);
    console.log('But registration itself completed successfully.');
  }
}

main();
