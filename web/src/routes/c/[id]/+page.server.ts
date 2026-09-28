import { error } from '@sveltejs/kit';

import vm from '../../../../../data/viewmodel.json';

// 事前生成の対象を明示する。リンクの巡回に頼ると、
// 一覧から辿れない項目が静かに欠ける。
export function entries() {
	return vm.items.map((i) => ({ id: i.concept_id }));
}

export function load({ params }) {
	const item = vm.items.find((i) => i.concept_id === params.id);
	if (!item) error(404, '該当する概念がありません');
	const n = vm.items.indexOf(item);
	return {
		item,
		index: n + 1,
		prev: n > 0 ? vm.items[n - 1] : null,
		next: n < vm.items.length - 1 ? vm.items[n + 1] : null
	};
}
