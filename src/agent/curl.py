import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

def center_crop_image(image, output_size):
    h, w = image.shape[1:]
    new_h, new_w = output_size, output_size

    top = (h - new_h)//2
    left = (w - new_w)//2

    image = image[:, top:top + new_h, left:left + new_w]
    return image

class CURL():
    def __init__(self, model, device, action_shape, args):
        self.model = model
        self.device = device
        self.actor_update_freq = args.actor_update_freq
        self.critic_target_update_freq = args.critic_target_update_freq
        self.curl_update_freq = args.curl_update_freq
        self.critic_tau = args.critic_tau
        self.encoder_tau = args.curl_encoder_tau
        self.image_size = args.agent_image_size
        self.log_interval = args.log_interval
        self.discount = args.discount
        self.detach_encoder = args.detach_encoder
        
        self.log_alpha = torch.tensor(np.log(args.init_temperature)).to(device)
        self.log_alpha.requires_grad = True
        self.target_entropy = -np.prod(action_shape)
        
        
        # optimizers
        self.actor_optimizer = torch.optim.Adam(
            self.model.actor.parameters(), lr=args.actor_lr, betas=(args.actor_beta, 0.999)
        )

        self.critic_optimizer = torch.optim.Adam(
            self.model.critic.parameters(), lr=args.critic_lr, betas=(args.critic_beta, 0.999)
        )

        self.log_alpha_optimizer = torch.optim.Adam(
            [self.log_alpha], lr=args.alpha_lr, betas=(args.alpha_beta, 0.999)
        )

        self.curl_optimizer = torch.optim.Adam(
                self.model.curl.parameters(), lr=args.curl_encoder_lr)
        self.cross_entropy_loss = nn.CrossEntropyLoss()
        
        self.train()
        self.model.critic_target.train()

    def train(self, training=True):
        self.training = training
        self.model.actor.train(training)
        self.model.critic.train(training)
        self.model.curl.train(training)

    @property
    def alpha(self):
        return self.log_alpha.exp()

    def select_action(self, obs):
        with torch.no_grad():
            obs = torch.FloatTensor(obs).to(self.device)
            obs = obs.unsqueeze(0)
            mu, _, _, _ = self.model.actor(
                obs, compute_pi=False, compute_log_pi=False
            )
            return mu.cpu().data.numpy().flatten()
    
    def sample_action(self, obs):
        if obs.shape[-1] != self.image_size:
            obs = center_crop_image(obs, self.image_size)
 
        with torch.no_grad():
            obs = torch.FloatTensor(obs).to(self.device)
            obs = obs.unsqueeze(0)
            mu, pi, _, _ = self.model.actor(obs, compute_log_pi=False)
            return pi.cpu().data.numpy().flatten()
    

    def update_critic(self, obs, action, reward, next_obs, not_done, L, step):
        with torch.no_grad():
            _, policy_action, log_pi, _ = self.model.actor(next_obs)
            target_Q1, target_Q2 = self.model.critic_target(next_obs, policy_action)
            target_V = torch.min(target_Q1,
                                 target_Q2) - self.alpha.detach() * log_pi
            target_Q = reward + (not_done * self.discount * target_V)

        # get current Q estimates
        current_Q1, current_Q2 = self.model.critic(
            obs, action, detach_encoder=self.detach_encoder)
        critic_loss = F.mse_loss(current_Q1,
                                 target_Q) + F.mse_loss(current_Q2, target_Q)
        if step % self.log_interval == 0:
            L.log('train_critic/loss', critic_loss, step)


        # Optimize the critic
        self.critic_optimizer.zero_grad()
        critic_loss.backward()
        self.critic_optimizer.step()

        self.model.critic.log(L, step)


    def update_actor_and_alpha(self, obs, L, step):
        # detach encoder, so we don't update it with the actor loss
        _, pi, log_pi, log_std = self.model.actor(obs, detach_encoder=True)
        actor_Q1, actor_Q2 = self.model.critic(obs, pi, detach_encoder=True)

        actor_Q = torch.min(actor_Q1, actor_Q2)
        actor_loss = (self.alpha.detach() * log_pi - actor_Q).mean()

        if step % self.log_interval == 0:
            L.log('train_actor/loss', actor_loss, step)
            L.log('train_actor/target_entropy', self.target_entropy, step)
        entropy = 0.5 * log_std.shape[1] * \
            (1.0 + np.log(2 * np.pi)) + log_std.sum(dim=-1)
        if step % self.log_interval == 0:                                    
            L.log('train_actor/entropy', entropy.mean(), step)

        # optimize the actor
        self.actor_optimizer.zero_grad()
        actor_loss.backward()
        self.actor_optimizer.step()

        self.model.actor.log(L, step)

        self.log_alpha_optimizer.zero_grad()
        alpha_loss = (self.alpha *
                      (-log_pi - self.target_entropy).detach()).mean()
        if step % self.log_interval == 0:
            L.log('train_alpha/loss', alpha_loss, step)
            L.log('train_alpha/value', self.alpha, step)
        alpha_loss.backward()
        self.log_alpha_optimizer.step()
        
    
    def update_curl(self, obs_anchor, obs_pos, L, step):
        
        z_a = self.model.curl.encode(obs_anchor)
        z_pos = self.model.curl.encode(obs_pos, ema=True)
        
        logits = self.model.curl.compute_logits(z_a, z_pos)
        labels = torch.arange(logits.shape[0]).long().to(self.device)
        loss = self.cross_entropy_loss(logits, labels)
        
        self.curl_optimizer.zero_grad()
        loss.backward()
        self.curl_optimizer.step()
        if step % self.log_interval == 0:
            L.log('train/curl_loss', loss, step)


    def update(self, replay_buffer, L, step):
        obs, action, reward, next_obs, not_done, cpc_kwargs = replay_buffer.sample_curl()
    
        if step % self.log_interval == 0:
            L.log('train/batch_reward', reward.mean(), step)

        self.update_critic(obs, action, reward, next_obs, not_done, L, step)

        if step % self.actor_update_freq == 0:
            self.update_actor_and_alpha(obs, L, step)

        if step % self.critic_target_update_freq == 0:
            self.model.soft_update_params(self.critic_tau, self.encoder_tau)
        
        if step % self.curl_update_freq == 0:
            obs_anchor, obs_pos = cpc_kwargs["obs_anchor"], cpc_kwargs["obs_pos"]
            self.update_curl(obs_anchor, obs_pos, L, step)