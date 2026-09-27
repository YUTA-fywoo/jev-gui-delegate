"""Regression checks derived from real-site failures; not live-site results."""
import time,unittest
from unittest.mock import patch
from gui_delegate.browser_guard import action_guard
from gui_delegate.drivers import observation
from gui_delegate.schema import Predicate,Control
from gui_delegate.security import Stop
from gui_delegate.tests.test_adaptive import setup,contract
from gui_delegate.tests.test_guards import button,cp

class RealSiteRegressions(unittest.TestCase):
    def test_recommendation_change_does_not_invalidate_selected_control(self):
        chosen=button('Search');other=button('Trending today','other')
        ctl,planner,driver=setup([chosen,other],after=[button('Done')])
        step=planner.plan(ctl.observe(),0)
        other.name='Another recommendation'
        ctl.perform(step,cp())
        self.assertEqual(driver.actions,1)

    def test_target_semantics_and_form_state_still_invalidate(self):
        chosen=button('Read article');chosen.attributes.update(href='https://fixture.invalid/article',dom_path='a:nth-of-type(1)',context='Results')
        field=Control(id='q',role='textbox',name='Search',value='cats',visible=True,enabled=True)
        original=observation(1,'https://fixture.invalid/',[chosen,field]);before=action_guard(original,'one')
        for attr,value in [('href','https://fixture.invalid/other'),('context','Advertisement'),('dom_path','a:nth-of-type(2)')]:
            changed=original.model_copy(deep=True);changed.controls[0].attributes[attr]=value
            self.assertNotEqual(before,action_guard(changed,'one'))
        changed=original.model_copy(deep=True);changed.controls[1].value='dogs'
        self.assertNotEqual(before,action_guard(changed,'one'))
        changed=original.model_copy(deep=True);changed.controls[0].frame_url='https://fixture.invalid/frame'
        self.assertNotEqual(before,action_guard(changed,'one'))

    def test_delayed_navigation_observed_without_second_click(self):
        ctl,planner,driver=setup([button('Open')]);step=planner.plan(ctl.observe(),0)
        step.after=[Predicate(kind='url_path',equals='/done')]
        real=driver.observe;post_reads=0
        def delayed():
            nonlocal post_reads
            obs=real()
            if driver.actions:
                post_reads+=1
                if post_reads>=7:obs=obs.model_copy(update={'location':'https://fixture.invalid/done','fingerprint':'b'*64})
            return obs
        driver.observe=delayed
        with patch('gui_delegate.controller.time.sleep'):
            ctl.perform(step,cp())
        self.assertEqual(driver.actions,1);self.assertEqual(post_reads,7)

    def test_redirected_detail_does_not_repeat_same_link(self):
        link=button('Note');link.role='link';link.attributes['href']='https://fixture.invalid/search/42'
        c=contract(success=[{'kind':'url_path','equals':'/search/42'}])
        ctl,planner,driver=setup([link],c)
        planner.plan(ctl.observe(),0)
        redirected=observation(20,'https://fixture.invalid/explore/42',[link,button('New recommendation','ad')])
        with self.assertRaisesRegex(Stop,'GOAL_DESTINATION_ALREADY_VISITED'):planner.plan(redirected,1)
        self.assertEqual(driver.actions,0)

if __name__=='__main__':unittest.main()
