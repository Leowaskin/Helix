const alphabet='ACGT';
export function encode(data, constrained=false){
 if(!constrained)return Array.from(data,v=>[6,4,2,0].map(s=>alphabet[(v>>s)&3]).join('')).join('');
 const memo=new Map();function count(n,last,run){if(!n)return 1;const key=[n,last,run].join();if(memo.has(key))return memo.get(key);let c=0;for(const b of alphabet)if(b!==last||run<3)c+=count(n-1,b,b===last?run+1:1);memo.set(key,c);return c;}
 let last='',run=0,out='';for(let rank of data)for(let rem=4;rem>=0;rem--)for(const b of alphabet){if(b===last&&run===3)continue;const r=b===last?run+1:1,ways=count(rem,b,r);if(rank<ways){out+=b;last=b;run=r;break;}rank-=ways;}return out;
}
